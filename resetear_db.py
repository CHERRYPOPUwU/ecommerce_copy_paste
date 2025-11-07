from ecom_login.app import app, db
from ecom_login.models import Usuario, Producto, CarritoItem, Pedido, DetallePedido, MetodoPago

def resetear_base_datos():
    with app.app_context():
        print("🗑️  Eliminando todas las tablas...")
        db.drop_all()
        
        print("✨ Creando nuevas tablas...")
        db.create_all()
        
        print("✅ ¡Base de datos reseteada correctamente!")
        print("\nTablas creadas:")
        print("   - usuarios")
        print("   - productos")
        print("   - carrito_items")
        print("   - pedidos")
        print("   - detalles_pedido")
        print("   - metodos_pago")
        
        # Crear usuario admin por defecto
        print("\n👤 Creando usuario administrador...")
        admin = Usuario(
            nombre="Administrador",
            correo="admin@tienda.com",
            rol="admin"
        )
        admin.set_password("admin123")
        db.session.add(admin)
        
        # Crear algunos productos de ejemplo
        print("📦 Creando productos de ejemplo...")
        productos = [
            Producto(
                nombre="Funko Pop Batman",
                descripcion="Figura coleccionable de Batman",
                precio=45000,
                stock=10,
                imagen="https://images.unsplash.com/photo-1608889335941-32ac5f2041b9?w=400"
            ),
            Producto(
                nombre="Funko Pop Iron Man",
                descripcion="Figura coleccionable de Iron Man",
                precio=50000,
                stock=8,
                imagen="https://images.unsplash.com/photo-1608889476561-6242cfdbf622?w=400"
            ),
            Producto(
                nombre="Funko Pop Spider-Man",
                descripcion="Figura coleccionable de Spider-Man",
                precio=48000,
                stock=15,
                imagen="https://images.unsplash.com/photo-1608889825103-eb5ed706fc64?w=400"
            ),
        ]
        
        for producto in productos:
            db.session.add(producto)
        
        db.session.commit()
        
        print("\n✅ ¡Todo listo! Puedes iniciar sesión con:")
        print("   Email: admin@tienda.com")
        print("   Contraseña: admin123")

if __name__ == '__main__':
    resetear_base_datos()