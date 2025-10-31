from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .config import Config
from .models import db, Usuario, Producto
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
        contraseña = request.form['contraseña']

        usuario = Usuario.query.filter_by(correo=correo).first()
        if usuario and check_password_hash(usuario.contraseña, contraseña):
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
        contraseña = request.form['contraseña']

        existente = Usuario.query.filter_by(correo=correo).first()
        if existente:
            flash('Este correo ya está registrado.', 'warning')
        else:
            nuevo = Usuario(nombre=nombre, correo=correo, rol='cliente')
            nuevo.set_password(contraseña)
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
        nueva = request.form['nueva']
        current_user.set_password(nueva)
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

    producto = Producto(nombre=nombre, descripcion=descripcion, precio=precio, stock=stock)
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

# ---------------------- EJECUCIÓN ----------------------
if __name__ == '__main__':
    app.run(debug=True)
