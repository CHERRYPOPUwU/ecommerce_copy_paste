from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    contrasena = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(20), default='cliente')  

    # Contraseñas seguras
    def set_password(self, password):
        self.contrasena = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.contrasena, password)

class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(200))
    precio = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    imagen = db.Column(db.String(255), nullable=True)

class Pedido(db.Model):
    __tablename__ = 'pedidos'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Float, nullable=False, default=0.0)
    estado = db.Column(db.String(20), default='Pendiente')

    usuario = db.relationship('Usuario', backref='pedidos', lazy=True)

    # relación hacia los detalles del pedido
    detalles = db.relationship('DetallePedido', backref='pedido_padre', lazy=True)


class DetallePedido(db.Model):
    __tablename__ = 'detalles_pedido'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)  
    
    producto = db.relationship('Producto', backref='detalles_pedido', lazy=True)

class MetodoPago(db.Model):
    __tablename__ = 'metodos_pago'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    tipo_pago = db.Column(db.String(50), nullable=False)  # 'tarjeta' o 'pse'
    estado_pago = db.Column(db.String(20), default='Pendiente')  # Pendiente, Aprobado, Rechazado
    
    # Campos para tarjeta
    numero_tarjeta = db.Column(db.String(4), nullable=True) 
    nombre_titular = db.Column(db.String(100), nullable=True)
    
    # Campos para PSE
    banco = db.Column(db.String(100), nullable=True)
    tipo_persona = db.Column(db.String(20), nullable=True)  # Natural o Jurídica
    tipo_documento = db.Column(db.String(20), nullable=True)
    numero_documento = db.Column(db.String(50), nullable=True)
    
    fecha_pago = db.Column(db.DateTime, default=datetime.utcnow)
    
    pedido = db.relationship('Pedido', backref='metodo_pago', lazy=True)
class CarritoItem(db.Model):
    __tablename__ = 'carrito_items'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'))
    cantidad = db.Column(db.Integer, default=1)

    usuario = db.relationship('Usuario', backref='carrito', lazy=True)
    producto = db.relationship('Producto', backref='carrito_items', lazy=True)
