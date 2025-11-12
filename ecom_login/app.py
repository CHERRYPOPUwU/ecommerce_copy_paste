from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .config import Config
from .models import db, Usuario, Producto, CarritoItem, Pedido, DetallePedido, MetodoPago
from app.utils.pagos_utils import verificar_propietario_pedido, verificar_y_actualizar_stock, registrar_pago_tarjeta, registrar_pago_pse
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
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('home'))
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


# ---------- ADMIN: CANCELAR PEDIDO ----------
@app.route('/admin/pedido/<int:pedido_id>/cancelar', methods=['POST'])
@login_required
def cancelar_pedido_admin(pedido_id):
    if current_user.rol != 'admin':
        flash(ACCESS_DENIED_MSG, 'danger')
        return redirect(url_for('home'))

    pedido = Pedido.query.get_or_404(pedido_id)
    
    # Solo se pueden cancelar pedidos que no estén entregados o ya cancelados
    if pedido.estado in ['Entregado', 'Cancelado']:
        flash(f'No se puede cancelar un pedido con estado "{pedido.estado}".', 'warning')
        return redirect(url_for('admin_pedidos'))
    
    try:
        # Si el pedido está confirmado (ya se descontó stock), devolver el stock
        if pedido.estado in ['Confirmado', 'Enviado']:
            detalles = DetallePedido.query.filter_by(pedido_id=pedido.id).all()
            for detalle in detalles:
                producto = Producto.query.get(detalle.producto_id)
                if producto:
                    producto.stock += detalle.cantidad
        
        # Cambiar estado a Cancelado
        pedido.estado = 'Cancelado'
        
        # Actualizar estado de pago si existe
        metodo_pago = MetodoPago.query.filter_by(pedido_id=pedido.id).first()
        if metodo_pago:
            metodo_pago.estado_pago = 'Cancelado'
        
        db.session.commit()
        flash(f'Pedido #{pedido.id} cancelado exitosamente. Stock restaurado.', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error al cancelar el pedido: {str(e)}', 'danger')
    
    return redirect(url_for('admin_pedidos'))


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.rol == 'admin':
        return redirect(url_for('admin_dashboard'))
    productos = Producto.query.all()
    return render_template('user/catalogo.html', productos=productos)


# ---------- ADMIN: NUEVO PRODUCTO ----------
@app.route('/admin/productos/nuevo', methods=['POST'])
@login_required
def nuevo_producto():
    if current_user.rol != 'admin':
        flash(ACCESS_DENIED_MSG, 'danger')
        return redirect(url_for('home'))

    try:
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = float(request.form['precio'])
        stock = int(request.form['stock'])
        imagen = request.form['imagen']
        
        # ✅ VALIDACIÓN: No permitir precios negativos
        if precio < 0:
            flash('❌ El precio no puede ser negativo.', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        # ✅ VALIDACIÓN: No permitir stock negativo
        if stock < 0:
            flash('❌ El stock no puede ser negativo.', 'danger')
            return redirect(url_for('admin_dashboard'))

        producto = Producto(
            nombre=nombre, 
            descripcion=descripcion, 
            precio=precio, 
            stock=stock, 
            imagen=imagen
        )
        db.session.add(producto)
        db.session.commit()
        flash('✅ Producto agregado correctamente.', 'success')
    except ValueError:
        flash('❌ Error: Precio y stock deben ser números válidos.', 'danger')
    except Exception as e:
        flash(f'❌ Error al agregar producto: {str(e)}', 'danger')
    
    return redirect(url_for('admin_dashboard'))


# ---------- ADMIN: EDITAR PRODUCTO ----------
@app.route('/admin/productos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_producto(id):
    # Verificar si el usuario tiene el rol de 'admin'
    if current_user.rol != 'admin':
        flash(ACCESS_DENIED_MSG, 'danger')
        return redirect(url_for('home'))

    # Obtener el producto desde la base de datos
    producto = Producto.query.get_or_404(id)

    if request.method == 'POST':
        try:
            # Obtener los datos del formulario
            nombre = request.form['nombre']
            descripcion = request.form['descripcion']
            precio = float(request.form['precio'])
            stock = int(request.form['stock'])
            imagen = request.form['imagen']

            # VALIDACIÓN: No permitir precios negativos
            if precio < 0:
                flash('❌ El precio no puede ser negativo.', 'danger')
                return redirect(url_for('editar_producto', id=id))

            # VALIDACIÓN: No permitir stock negativo
            if stock < 0:
                flash('❌ El stock no puede ser negativo.', 'danger')
                return redirect(url_for('editar_producto', id=id))

            # VALIDACIÓN: Nombre debe tener una longitud mínima (si es necesario)
            if len(nombre) < 3:
                flash('❌ El nombre del producto debe tener al menos 3 caracteres.', 'danger')
                return redirect(url_for('editar_producto', id=id))

            # VALIDACIÓN: Descripción debe tener una longitud mínima (si es necesario)
            if len(descripcion) < 5:
                flash('❌ La descripción debe tener al menos 5 caracteres.', 'danger')
                return redirect(url_for('editar_producto', id=id))

            # Actualizar el producto con los nuevos datos
            producto.nombre = nombre
            producto.descripcion = descripcion
            producto.precio = precio
            producto.stock = stock
            producto.imagen = imagen

            # Guardar los cambios en la base de datos
            db.session.commit()
            flash('✅ Producto actualizado correctamente.', 'success')

            # Redirigir al dashboard de admin
            return redirect(url_for('admin_dashboard'))

        except ValueError:
            flash('❌ Error: Precio y stock deben ser números válidos.', 'danger')
        except Exception as e:
            flash(f'❌ Error al actualizar producto: {str(e)}', 'danger')

    # Si es GET, solo mostrar el formulario de edición
    return render_template('admin/editar_producto.html', producto=producto)


# ---------- ADMIN: ELIMINAR PRODUCTO ----------
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


# ---------------------- FUNCIÓN AUXILIAR PARA CALCULAR STOCK DISPONIBLE ----------------------
def obtener_stock_real(producto_id):
    """
    Devuelve el stock REAL del producto (sin reservas).
    Este es el stock físico que hay en el inventario.
    """
    producto = Producto.query.get(producto_id)
    if not producto:
        return 0
    
    return producto.stock


# ---------------------- CARRITO DE COMPRAS ----------------------
@app.route('/carrito')
@login_required
def ver_carrito():
    items = CarritoItem.query.filter_by(usuario_id=current_user.id).all()
    
    # Verificar disponibilidad de cada item
    advertencias = []
    items_validos = []
    
    for item in items:
        stock_real = obtener_stock_real(item.producto_id)
        
        if stock_real <= 0:
            # Producto agotado - eliminar del carrito
            advertencias.append(
                f'❌ {item.producto.nombre} está agotado y fue eliminado de tu carrito.'
            )
            db.session.delete(item)
        elif item.cantidad > stock_real:
            # Ajustar cantidad al stock disponible
            advertencias.append(
                f'⚠ {item.producto.nombre}: Solo hay {stock_real} unidades disponibles. '
                f'Se ajustó la cantidad en tu carrito.'
            )
            item.cantidad = stock_real
            items_validos.append(item)
        else:
            items_validos.append(item)
    
    if advertencias:
        db.session.commit()
    
    for advertencia in advertencias:
        flash(advertencia, 'warning')
    
    total = sum(item.producto.precio * item.cantidad for item in items_validos)
    return render_template('user/carrito.html', items=items_validos, total=total)


@app.route('/carrito/agregar/<int:producto_id>', methods=['POST'])
@login_required
def agregar_carrito(producto_id):
    # Obtener el producto
    producto = Producto.query.get_or_404(producto_id)
    
    # Obtener cantidad del formulario (por defecto 1)
    try:
        cantidad = int(request.form.get('cantidad', 1))
        if cantidad < 1:
            cantidad = 1
    except ValueError:
        cantidad = 1
    
    # ✅ Obtener el stock REAL (físico)
    stock_real = obtener_stock_real(producto_id)
    
    if stock_real <= 0:
        flash('❌ Este producto está agotado.', 'danger')
        return redirect(url_for('home'))
    
    # Verificar si ya existe en el carrito
    item = CarritoItem.query.filter_by(
        usuario_id=current_user.id, 
        producto_id=producto_id
    ).first()
    
    if item:
        # Verificar que no exceda el stock real
        nueva_cantidad = item.cantidad + cantidad
        if nueva_cantidad > stock_real:
            flash(
                f'⚠ No hay suficiente stock de {producto.nombre}. '
                f'Stock disponible: {stock_real}. Ya tienes {item.cantidad} en tu carrito.',
                'warning'
            )
            return redirect(url_for('home'))
        item.cantidad = nueva_cantidad
    else:
        # Verificar que la cantidad no exceda el stock real
        if cantidad > stock_real:
            flash(
                f'⚠ Solo hay {stock_real} unidades disponibles de {producto.nombre}.',
                'warning'
            )
            cantidad = stock_real
        
        nuevo = CarritoItem(
            usuario_id=current_user.id, 
            producto_id=producto_id, 
            cantidad=cantidad
        )
        db.session.add(nuevo)
    
    db.session.commit()
    
    if cantidad == 1:
        flash(f'✅ {producto.nombre} agregado al carrito 🛒', 'success')
    else:
        flash(f'✅ {cantidad} unidades de {producto.nombre} agregadas al carrito 🛒', 'success')
    
    return redirect(url_for('home'))


@app.route('/carrito/actualizar/<int:item_id>', methods=['POST'])
@login_required
def actualizar_cantidad_carrito(item_id):
    item = CarritoItem.query.get_or_404(item_id)
    
    if item.usuario_id != current_user.id:
        flash('Acción no permitida.', 'danger')
        return redirect(url_for('ver_carrito'))
    
    try:
        nueva_cantidad = int(request.form.get('cantidad', 1))
        if nueva_cantidad < 1:
            nueva_cantidad = 1
        
        # ✅ Verificar stock REAL
        stock_real = obtener_stock_real(item.producto_id)
        
        if nueva_cantidad > stock_real:
            flash(
                f'⚠ Solo hay {stock_real} unidades disponibles de {item.producto.nombre}.',
                'warning'
            )
            nueva_cantidad = stock_real if stock_real > 0 else 1
        
        item.cantidad = nueva_cantidad
        db.session.commit()
        flash('✅ Cantidad actualizada.', 'success')
    
    except ValueError:
        flash('❌ Cantidad inválida.', 'danger')
    
    return redirect(url_for('ver_carrito'))


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


# ---------- FINALIZAR COMPRA ----------
@app.route('/finalizar_compra', methods=['POST'])
@login_required
def finalizar_compra():
    try:
        carrito = CarritoItem.query.filter_by(usuario_id=current_user.id).all()
        if not carrito:
            flash('❌ Tu carrito está vacío.', 'warning')
            return redirect(url_for('ver_carrito'))

        # ✅ VALIDACIÓN CRÍTICA: Verificar stock REAL de cada producto
        productos_sin_stock = []
        for item in carrito:
            stock_real = obtener_stock_real(item.producto_id)
            
            if stock_real <= 0:
                productos_sin_stock.append(item.producto.nombre)
            elif stock_real < item.cantidad:
                flash(
                    f'⚠ No hay suficiente stock de {item.producto.nombre}. '
                    f'Stock disponible: {stock_real}. Por favor ajusta la cantidad.',
                    'danger'
                )
                return redirect(url_for('ver_carrito'))
        
        # Si hay productos sin stock, eliminarlos del carrito
        if productos_sin_stock:
            for item in carrito:
                if item.producto.nombre in productos_sin_stock:
                    db.session.delete(item)
            db.session.commit()
            
            flash(
                f'❌ Los siguientes productos están agotados y fueron eliminados: '
                f'{", ".join(productos_sin_stock)}. Por favor revisa tu carrito.',
                'danger'
            )
            return redirect(url_for('ver_carrito'))

        total = sum(item.producto.precio * item.cantidad for item in carrito)

        # Crear pedido con estado "Pendiente de Pago"
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
        flash(f'❌ Error al procesar el pedido: {str(e)}', 'danger')
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
    
    # Verificar que el usuario sea el propietario del pedido
    if not verificar_propietario_pedido(pedido):
        flash('❌ No tienes acceso a este pedido.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        # Obtener los datos del formulario
        numero_tarjeta = request.form.get('numero_tarjeta', '')
        nombre_titular = request.form.get('nombre_titular', '')
        cvv = request.form.get('cvv', '')

        # Validación de tarjeta y CVV
        if len(numero_tarjeta) != 16 or len(cvv) != 3:
            flash('❌ Datos de tarjeta inválidos. Asegúrate de que la tarjeta tenga 16 dígitos y el CVV 3 dígitos.', 'danger')
            return redirect(url_for('pago_tarjeta', pedido_id=pedido.id))

        # Validación usando el algoritmo Luhn para verificar el número de tarjeta
        if not verificar_tarjeta_luhn(numero_tarjeta):
            flash('❌ Número de tarjeta inválido. Por favor revisa el número de tu tarjeta.', 'danger')
            return redirect(url_for('pago_tarjeta', pedido_id=pedido.id))

        try:
            # Verificar si el stock está disponible antes de procesar el pago
            if not verificar_y_actualizar_stock(pedido):
                flash('❌ No hay suficiente stock para completar tu pedido.', 'danger')
                return redirect(url_for('ver_carrito'))

            # Procesar el pago
            registrar_pago_tarjeta(pedido, numero_tarjeta, nombre_titular)
            flash('¡Pago con tarjeta procesado exitosamente! 🎉', 'success')

            # Redirigir a la página de confirmación del pago
            return redirect(url_for('confirmacion_pago', pedido_id=pedido.id))

        except Exception as e:
            db.session.rollback()  # Rollback de cualquier cambio en caso de error
            flash(f'❌ Error al procesar el pago: {str(e)}', 'danger')
            return redirect(url_for('pago_tarjeta', pedido_id=pedido.id))

    # Si es GET, mostrar el formulario de pago
    return render_template('user/pago_tarjeta.html', pedido=pedido)

def verificar_tarjeta_luhn(numero_tarjeta):
    """
    Verifica si el número de tarjeta es válido utilizando el algoritmo Luhn.
    """
    suma = 0
    invertir_tarjeta = numero_tarjeta[::-1]
    
    for i, digito in enumerate(invertir_tarjeta):
        n = int(digito)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        suma += n
    
    return suma % 10 == 0


# ---------- PAGO CON PSE ----------
@app.route('/pago/pse/<int:pedido_id>', methods=['GET', 'POST'])
@login_required
def pago_pse(pedido_id):
    # Obtener el pedido desde la base de datos
    pedido = Pedido.query.get_or_404(pedido_id)
    
    # Verificar que el usuario sea el propietario del pedido
    if not verificar_propietario_pedido(pedido):
        flash('❌ No tienes acceso a este pedido.', 'danger')
        return redirect(url_for('home'))

    # Lista de bancos disponibles para el pago
    bancos = [
        'Bancolombia', 'Banco de Bogotá', 'BBVA Colombia', 'Davivienda',
        'Banco de Occidente', 'Banco Popular', 'Itaú', 'Banco Caja Social',
        'Banco AV Villas', 'Banco Falabella', 'Scotiabank Colpatria'
    ]

    if request.method == 'POST':
        # Obtener los datos del formulario
        banco = request.form.get('banco')
        tipo_persona = request.form.get('tipo_persona')
        tipo_documento = request.form.get('tipo_documento')
        numero_documento = request.form.get('numero_documento')

        # Validación de campos requeridos
        if not all([banco, tipo_persona, tipo_documento, numero_documento]):
            flash('❌ Por favor completa todos los campos.', 'danger')
            return redirect(url_for('pago_pse', pedido_id=pedido.id))

        # Validación: Verificar si el banco seleccionado es válido
        if banco not in bancos:
            flash('❌ El banco seleccionado no es válido.', 'danger')
            return redirect(url_for('pago_pse', pedido_id=pedido.id))

        # Validación del número de documento (puedes personalizar según el tipo de documento)
        if not numero_documento.isdigit():
            flash('❌ El número de documento debe ser un valor numérico.', 'danger')
            return redirect(url_for('pago_pse', pedido_id=pedido.id))

        try:
            # Verificar si el stock está disponible antes de procesar el pago
            if not verificar_y_actualizar_stock(pedido):
                flash('❌ No hay suficiente stock para completar tu pedido.', 'danger')
                return redirect(url_for('ver_carrito'))

            # Procesar el pago PSE
            registrar_pago_pse(pedido, banco, tipo_persona, tipo_documento, numero_documento)
            flash('¡Pago PSE procesado exitosamente! 🎉', 'success')

            # Redirigir a la página de confirmación del pago
            return redirect(url_for('confirmacion_pago', pedido_id=pedido.id))

        except Exception as e:
            db.session.rollback()  # Rollback de cualquier cambio en caso de error
            flash(f'❌ Error al procesar el pago: {str(e)}', 'danger')
            return redirect(url_for('pago_pse', pedido_id=pedido.id))

    # Si es GET, mostrar el formulario de pago
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


# ---------------------- EJECUCIÓN ----------------------
if __name__ == '__main__':
    app.run(debug=True)
