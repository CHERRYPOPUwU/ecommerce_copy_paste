from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .config import Config
from .models import db, Usuario, Producto, CarritoItem, Pedido, DetallePedido, MetodoPago
from dotenv import load_dotenv
import os

# ---------------------- CONFIGURACIÓN INICIAL ----------------------
app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
with app.app_context():
    db.create_all()

# config/messages.py
ACCESS_DENIED_MSG = "Acceso denegado."


# ---------------------- CONFIGURACIÓN DE LOGIN ----------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# ---------------------- RUTAS ----------------------
@app.route('/')
@login_required
def home():
    productos = Producto.query.all()
    return render_template('user/catalogo.html', nombre=current_user.correo, productos=productos)


# ---------- LOGIN ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        contrasena = request.form['contraseña']

        usuario = Usuario.query.filter_by(correo=correo).first()
        if usuario and check_password_hash(usuario.contrasena, contrasena):
            login_user(usuario)
            flash('Has iniciado sesión correctamente.', 'success')

            # Redirigir según rol
            if usuario.rol == 'admin':
                return redirect(url_for('admin_dashboard'))  # <-- ruta del panel admin
            else:
                return redirect(url_for('home'))  # <-- vista de cliente

        else:
            flash('Correo o contraseña incorrectos.', 'danger')

    return render_template('login.html')

# ---------- REGISTRO ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        contrasena = request.form['contraseña']

        existente = Usuario.query.filter_by(correo=correo).first()
        if existente:
            flash('Este correo ya está registrado.', 'warning')
        else:
            nuevo = Usuario(nombre=nombre, correo=correo, rol='cliente')
            nuevo.set_password(contrasena)
            db.session.add(nuevo)
            db.session.commit()
            flash('Registro exitoso. Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

# ---------- CAMBIO DE CONTRASEÑA ----------
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        actual = request.form['actual']
        nueva = request.form['nueva']
        confirmar = request.form['confirmar']

        # Validar contraseña actual
        if not check_password_hash(current_user.contrasena, actual):
            flash('La contraseña actual es incorrecta.', 'danger')
            return redirect(url_for('change_password'))

        if nueva != confirmar:
            flash('Las contraseñas nuevas no coinciden.', 'warning')
            return redirect(url_for('change_password'))

        # Actualizar contraseña
        current_user.contrasena = generate_password_hash(nueva)
        db.session.commit()
        flash('Contraseña actualizada correctamente.', 'success')
        return redirect(url_for('home'))

    return render_template('cambio_pass.html')

# ---------- AJUSTES DE USUARIO ----------
@app.route('/ajustes', methods=['GET', 'POST'])
@login_required
def ajustes_usuario():
    if request.method == 'POST':
        nuevo_correo = request.form['nuevo_correo']
        existente = Usuario.query.filter_by(correo=nuevo_correo).first()
        if existente:
            flash('Ese correo ya está en uso.', 'warning')
        else:
            current_user.correo = nuevo_correo
            db.session.commit()
            flash('Correo actualizado correctamente.', 'success')
            return redirect(url_for('home'))

    return render_template('ajustes.html', correo_actual=current_user.correo)

# ---------- LOGOUT ----------
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('login'))


# ---------------------ADMINISTRADOR-----------------------

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.rol != 'admin':
        flash('No tienes permiso para acceder a esta sección.', 'danger')
        return redirect(url_for('home'))

    productos = Producto.query.all()
    return render_template('admin/dashboard.html', productos=productos)


# ---------- ADMIN: LISTAR PEDIDOS ----------
@app.route('/admin/pedidos')
@login_required
def admin_pedidos():
    if current_user.rol != 'admin':
        flash(ACCESS_DENIED_MSG, 'danger')
        return redirect(url_for('home'))

    pedidos = Pedido.query.order_by(Pedido.fecha.desc()).all()
    return render_template('admin/pedidos.html', pedidos=pedidos)


# ---------- ADMIN: VER DETALLE DE PEDIDO ----------
@app.route('/admin/pedido/<int:pedido_id>')
@login_required
def admin_detalle_pedido(pedido_id):
    if current_user.rol != 'admin':
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('home'))
    
    pedido = Pedido.query.get_or_404(pedido_id)
    return render_template('admin/detalle_pedido_admin.html', pedido=pedido)


# ---------- ADMIN: CAMBIAR ESTADO ----------
@app.route('/admin/pedido/<int:pedido_id>/estado', methods=['POST'])
@login_required
def cambiar_estado_pedido(pedido_id):
    if current_user.rol != 'admin':
        flash(ACCESS_DENIED_MSG, 'danger')
        return redirect(url_for('home'))

    pedido = Pedido.query.get_or_404(pedido_id)
    nuevo_estado = request.form['estado']
    pedido.estado = nuevo_estado
    db.session.commit()

    flash(f'Estado del pedido #{pedido.id} actualizado a "{nuevo_estado}".', 'success')
    return redirect(url_for('admin_pedidos'))


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.rol == 'admin':
        return redirect(url_for('admin_dashboard'))
    productos = Producto.query.all()
    return render_template('user/catalogo.html', productos=productos)


@app.route('/admin/productos/nuevo', methods=['POST'])
@login_required
def nuevo_producto():
    if current_user.rol != 'admin':
        flash(ACCESS_DENIED_MSG, 'danger')
        return redirect(url_for('home'))

    nombre = request.form['nombre']
    descripcion = request.form['descripcion']
    precio = float(request.form['precio'])
    stock = int(request.form['stock'])
    imagen = request.form['imagen'] 

    producto = Producto(nombre=nombre, descripcion=descripcion, precio=precio, stock=stock, imagen=imagen)
    db.session.add(producto)
    db.session.commit()
    flash('Producto agregado correctamente.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/productos/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_producto(id):
    if current_user.rol != 'admin':
        flash(ACCESS_DENIED_MSG, 'danger')
        return redirect(url_for('home'))

    producto = Producto.query.get_or_404(id)
    db.session.delete(producto)
    db.session.commit()
    flash('Producto eliminado.', 'info')
    return redirect(url_for('admin_dashboard'))


# ---------------------- CARRITO DE COMPRAS ----------------------
@app.route('/carrito')
@login_required
def ver_carrito():
    items = CarritoItem.query.filter_by(usuario_id=current_user.id).all()
    total = sum(item.producto.precio * item.cantidad for item in items)
    return render_template('user/carrito.html', items=items, total=total)


@app.route('/carrito/agregar/<int:producto_id>', methods=['POST'])
@login_required
def agregar_carrito(producto_id):
    # Obtener el producto
    producto = Producto.query.get_or_404(producto_id)
    
    # Verificar si hay stock disponible
    if producto.stock <= 0:
        flash('Este producto está agotado.', 'danger')
        return redirect(url_for('home'))
    
    # Verificar si ya existe en el carrito
    item = CarritoItem.query.filter_by(
        usuario_id=current_user.id, 
        producto_id=producto_id
    ).first()
    
    if item:
        # Verificar que no exceda el stock disponible
        if item.cantidad + 1 > producto.stock:
            flash(f'No hay más stock disponible de {producto.nombre}. Stock actual: {producto.stock}', 'warning')
            return redirect(url_for('home'))
        item.cantidad += 1
    else:
        nuevo = CarritoItem(
            usuario_id=current_user.id, 
            producto_id=producto_id, 
            cantidad=1
        )
        db.session.add(nuevo)
    
    db.session.commit()
    flash(f' {producto.nombre} agregado al carrito 🛒', 'success')
    return redirect(url_for('home'))

@app.route('/carrito/eliminar/<int:item_id>')
@login_required
def eliminar_item(item_id):
    item = CarritoItem.query.get_or_404(item_id)
    if item.usuario_id != current_user.id:
        flash('Acción no permitida.', 'danger')
        return redirect(url_for('ver_carrito'))
    db.session.delete(item)
    db.session.commit()
    flash('Producto eliminado del carrito.', 'info')
    return redirect(url_for('ver_carrito'))

@app.route('/carrito/vaciar')
@login_required
def vaciar_carrito():
    CarritoItem.query.filter_by(usuario_id=current_user.id).delete()
    db.session.commit()
    flash('Carrito vaciado correctamente.', 'info')
    return redirect(url_for('ver_carrito'))


# Finalizar la compra
@app.route('/finalizar_compra', methods=['POST'])
@login_required
def finalizar_compra():
    try:
        carrito = CarritoItem.query.filter_by(usuario_id=current_user.id).all()
        if not carrito:
            flash('Tu carrito está vacío.', 'warning')
            return redirect(url_for('ver_carrito'))

        for item in carrito:
            if item.producto.stock < item.cantidad:
                flash(f'No hay suficiente stock de {item.producto.nombre}. Stock disponible: {item.producto.stock}', 'danger')
                return redirect(url_for('ver_carrito'))

        total = sum(item.producto.precio * item.cantidad for item in carrito)

        # Crear pedido
        pedido = Pedido(usuario_id=current_user.id, total=total, estado='Pendiente de Pago')
        db.session.add(pedido)
        db.session.commit()

        # Guardar detalles CON subtotal
        for item in carrito:
            subtotal_calculado = item.producto.precio * item.cantidad
            detalle = DetallePedido(
                pedido_id=pedido.id,
                producto_id=item.producto_id,
                cantidad=item.cantidad,
                precio=item.producto.precio,
                subtotal=subtotal_calculado
            )
            db.session.add(detalle)

        db.session.commit()

        # Guardar ID del pedido en sesión y redirigir a selección de pago
        session['pedido_pendiente'] = pedido.id
        return redirect(url_for('seleccionar_metodo_pago'))
    
    except Exception as e:
        db.session.rollback()
        print(f"ERROR en finalizar_compra: {str(e)}")
        flash(f'Error al procesar el pedido: {str(e)}', 'danger')
        return redirect(url_for('ver_carrito'))

# ---------- SELECCIONAR MÉTODO DE PAGO ----------
@app.route('/pago/metodo')
@login_required
def seleccionar_metodo_pago():
    pedido_id = session.get('pedido_pendiente')
    if not pedido_id:
        flash('No hay ningún pedido pendiente.', 'warning')
        return redirect(url_for('ver_carrito'))
    
    pedido = Pedido.query.get_or_404(pedido_id)
    return render_template('user/seleccionar_pago.html', pedido=pedido)


# ---------- PAGO CON TARJETA ----------
@app.route('/pago/tarjeta/<int:pedido_id>', methods=['GET', 'POST'])
@login_required
def pago_tarjeta(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    
    if pedido.usuario_id != current_user.id:
        flash(ACCESS_DENIED_MSG, 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        # Obtener datos 
        numero_tarjeta = request.form['numero_tarjeta']
        nombre_titular = request.form['nombre_titular']
        fecha_expiracion = request.form['fecha_expiracion']
        cvv = request.form['cvv']
        
        # Validación básica 
        if len(numero_tarjeta) == 16 and len(cvv) == 3:
            try:
                # reducir stock
                detalles = DetallePedido.query.filter_by(pedido_id=pedido.id).all()
                for detalle in detalles:
                    producto = Producto.query.get(detalle.producto_id)
                    if producto:
                        
                        if producto.stock >= detalle.cantidad:
                            producto.stock -= detalle.cantidad
                        else:
                            flash(f'No hay suficiente stock de {producto.nombre}', 'danger')
                            return redirect(url_for('pago_tarjeta', pedido_id=pedido.id))
                
                # Guardar método de pago
                metodo = MetodoPago(
                    pedido_id=pedido.id,
                    tipo_pago='tarjeta',
                    estado_pago='Aprobado',
                    numero_tarjeta=numero_tarjeta[-4:], #protege el numero
                    nombre_titular=nombre_titular
                )
                db.session.add(metodo)
                
                # Actualizar estado del pedido
                pedido.estado = 'Confirmado'
                
                # Limpiar carrito
                CarritoItem.query.filter_by(usuario_id=current_user.id).delete()
                
                db.session.commit()
                
                # Limpiar sesión
                session.pop('pedido_pendiente', None)
                
                flash('¡Pago procesado exitosamente!', 'success')
                return redirect(url_for('confirmacion_pago', pedido_id=pedido.id))
            
            except Exception as e:
                db.session.rollback()
                flash(f'Error al procesar el pago: {str(e)}', 'danger')
                return redirect(url_for('pago_tarjeta', pedido_id=pedido.id))
        else:
            flash('Datos de tarjeta inválidos.', 'danger')
    
    return render_template('user/pago_tarjeta.html', pedido=pedido)


# ---------- PAGO CON PSE ----------
@app.route('/pago/pse/<int:pedido_id>', methods=['GET', 'POST'])
@login_required
def pago_pse(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    
    if pedido.usuario_id != current_user.id:
        flash(ACCESS_DENIED_MSG, 'danger')
        return redirect(url_for('home'))
    
    # Lista de bancos
    bancos = [
        'Bancolombia', 'Banco de Bogotá', 'BBVA Colombia', 'Davivienda',
        'Banco de Occidente', 'Banco Popular', 'Itaú', 'Banco Caja Social',
        'Banco AV Villas', 'Banco Falabella', 'Scotiabank Colpatria'
    ]
    
    if request.method == 'POST':
        banco = request.form['banco']
        tipo_persona = request.form['tipo_persona']
        tipo_documento = request.form['tipo_documento']
        numero_documento = request.form['numero_documento']
        
        # Validación 
        if banco and tipo_persona and numero_documento:
            try:
                # REDUCIR STOCK 
                detalles = DetallePedido.query.filter_by(pedido_id=pedido.id).all()
                for detalle in detalles:
                    producto = Producto.query.get(detalle.producto_id)
                    if producto:
                        
                        if producto.stock >= detalle.cantidad:
                            producto.stock -= detalle.cantidad
                        else:
                            flash(f'No hay suficiente stock de {producto.nombre}', 'danger')
                            return redirect(url_for('pago_pse', pedido_id=pedido.id))
                
                # Guardar método de pago
                metodo = MetodoPago(
                    pedido_id=pedido.id,
                    tipo_pago='pse',
                    estado_pago='Aprobado',
                    banco=banco,
                    tipo_persona=tipo_persona,
                    tipo_documento=tipo_documento,
                    numero_documento=numero_documento[-4:]  #protege el numero
                )
                db.session.add(metodo)
                
                # Actualizar 
                pedido.estado = 'Confirmado'
                
                # Limpiar carrito
                CarritoItem.query.filter_by(usuario_id=current_user.id).delete()
                
                db.session.commit()
                
                # Limpiar sesión
                session.pop('pedido_pendiente', None)
                
                flash('¡Pago PSE procesado exitosamente!', 'success')
                return redirect(url_for('confirmacion_pago', pedido_id=pedido.id))
            
            except Exception as e:
                db.session.rollback()
                flash(f'Error al procesar el pago: {str(e)}', 'danger')
                return redirect(url_for('pago_pse', pedido_id=pedido.id))
        else:
            flash('Por favor completa todos los campos.', 'danger')
    
    return render_template('user/pago_pse.html', pedido=pedido, bancos=bancos)


# ---------- CONFIRMACIÓN DE PAGO ----------
@app.route('/pago/confirmacion/<int:pedido_id>')
@login_required
def confirmacion_pago(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    
    if pedido.usuario_id != current_user.id:
        flash(ACCESS_DENIED_MSG, 'danger')
        return redirect(url_for('home'))
    
    metodo = MetodoPago.query.filter_by(pedido_id=pedido.id).first()
    return render_template('user/confirmacion_pago.html', pedido=pedido, metodo=metodo)

    # Limpiar el carrito
    for item in carrito:
        db.session.delete(item)

    db.session.commit()

    flash('Pedido finalizado correctamente.', 'success')
    return redirect(url_for('mis_pedidos'))


# ---------- MIS PEDIDOS ----------
@app.route('/mis_pedidos')
@login_required
def mis_pedidos():
    pedidos = Pedido.query.filter_by(usuario_id=current_user.id).all()
    return render_template('user/mis_pedidos.html', pedidos=pedidos)


# ---------- DETALLE DE PEDIDO ----------
@app.route('/pedido/<int:pedido_id>')
@login_required
def detalle_pedido(pedido_id):
    pedido = Pedido.query.filter_by(id=pedido_id, usuario_id=current_user.id).first_or_404()
    detalles = DetallePedido.query.filter_by(pedido_id=pedido.id).all()
    return render_template('user/detalle_pedido.html', pedido=pedido, detalles=detalles)


# ---------- EDITAR PRODUCTO ----------
@app.route('/admin/productos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_producto(id):
    if current_user.rol != 'admin':
        flash(ACCESS_DENIED_MSG, 'danger')
        return redirect(url_for('home'))

    producto = Producto.query.get_or_404(id)

    if request.method == 'POST':
        producto.nombre = request.form['nombre']
        producto.descripcion = request.form['descripcion']
        producto.precio = float(request.form['precio'])
        producto.stock = int(request.form['stock'])
        producto.imagen = request.form['imagen']
        db.session.commit()
        flash('Producto actualizado correctamente.', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/editar_producto.html', producto=producto)


# ---------------------- EJECUCIÓN ----------------------
if __name__ == '__main__':
    app.run(debug=True)
