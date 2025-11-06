from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .config import Config
from .models import db, Usuario, Producto, CarritoItem, Pedido, DetallePedido
from dotenv import load_dotenv
import os

# ---------------------- CONFIGURACIÓN INICIAL ----------------------
app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
with app.app_context():
    db.create_all()

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
    if current_user.rol == 'admin':
        return render_template('admin/dashboard.html', nombre=current_user.correo)
    
    # Si no es admin, mostrar los productos
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
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('home'))

    pedidos = Pedido.query.order_by(Pedido.fecha.desc()).all()
    return render_template('admin/pedidos.html', pedidos=pedidos)


# ---------- ADMIN: CAMBIAR ESTADO ----------
@app.route('/admin/pedido/<int:pedido_id>/estado', methods=['POST'])
@login_required
def cambiar_estado_pedido(pedido_id):
    if current_user.rol != 'admin':
        flash('Acceso denegado.', 'danger')
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
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('home'))

    nombre = request.form['nombre']
    descripcion = request.form['descripcion']
    precio = float(request.form['precio'])
    stock = int(request.form['stock'])
    imagen = request.form['imagen']  # nuevo campo

    producto = Producto(nombre=nombre, descripcion=descripcion, precio=precio, stock=stock, imagen=imagen)
    db.session.add(producto)
    db.session.commit()
    flash('Producto agregado correctamente.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/productos/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_producto(id):
    if current_user.rol != 'admin':
        flash('Acceso denegado.', 'danger')
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
    item = CarritoItem.query.filter_by(usuario_id=current_user.id, producto_id=producto_id).first()
    if item:
        item.cantidad += 1
    else:
        nuevo = CarritoItem(usuario_id=current_user.id, producto_id=producto_id, cantidad=1)
        db.session.add(nuevo)
    db.session.commit()
    flash('Producto agregado al carrito 🛒', 'success')
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


# ---------- FINALIZAR COMPRA ----------
@app.route('/finalizar_compra', methods=['POST'])
@login_required
def finalizar_compra():
    carrito = session.get('carrito', {})
    if not carrito:
        flash('Tu carrito está vacío.', 'warning')
        return redirect(url_for('carrito'))

    total = sum(item['precio'] * item['cantidad'] for item in carrito.values())

    nuevo_pedido = Pedido(usuario_id=current_user.id, total=total)
    db.session.add(nuevo_pedido)
    db.session.commit()

    for item in carrito.values():
        detalle = DetallePedido(
            pedido_id=nuevo_pedido.id,
            producto_id=item['id'],
            cantidad=item['cantidad'],
            subtotal=item['precio'] * item['cantidad']
        )
        db.session.add(detalle)

    db.session.commit()
    session['carrito'] = {}  # Vaciar carrito
    flash('Compra realizada con éxito. ¡Gracias por tu pedido!', 'success')
    return redirect(url_for('mis_pedidos'))


# ---------- MIS PEDIDOS ----------
@app.route('/mis_pedidos')
@login_required
def mis_pedidos():
    pedidos = Pedido.query.filter_by(usuario_id=current_user.id).order_by(Pedido.fecha.desc()).all()
    return render_template('mis_pedidos.html', pedidos=pedidos)


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
        flash('Acceso denegado.', 'danger')
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
