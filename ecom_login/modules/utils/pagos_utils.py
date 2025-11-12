from flask import flash, session
from flask_login import current_user
from ecom_login.models import db, Producto, DetallePedido, CarritoItem, MetodoPago


# ---------- FUNCIONES COMUNES ----------

def verificar_propietario_pedido(pedido):
    """Verifica que el pedido pertenezca al usuario actual."""
    if pedido.usuario_id != current_user.id:
        flash("Acceso denegado.", "danger")
        return False
    return True


def verificar_y_actualizar_stock(pedido):
    """Verifica stock de productos antes de confirmar y actualiza inventario."""
    detalles = DetallePedido.query.filter_by(pedido_id=pedido.id).all()
    for detalle in detalles:
        producto = Producto.query.get(detalle.producto_id)
        if producto:
            if producto.stock < detalle.cantidad:
                flash(
                    f"❌ Lo sentimos, {producto.nombre} no tiene suficiente stock. "
                    f"Disponible: {producto.stock}.",
                    "danger",
                )
                return False
            # ✅ Reducir el stock sin permitir negativos
            producto.stock = max(producto.stock - detalle.cantidad, 0)
    return True


def limpiar_carrito_y_sesion(usuario_id):
    """Vacía el carrito y elimina la sesión de pedido pendiente."""
    CarritoItem.query.filter_by(usuario_id=usuario_id).delete()
    session.pop("pedido_pendiente", None)


# ---------- FUNCIONES ESPECÍFICAS DE PAGO ----------

def registrar_pago_tarjeta(pedido, numero_tarjeta, nombre_titular):
    """Registra el pago con tarjeta."""
    metodo = MetodoPago(
        pedido_id=pedido.id,
        tipo_pago="tarjeta",
        estado_pago="Aprobado",
        numero_tarjeta=numero_tarjeta[-4:],
        nombre_titular=nombre_titular,
    )
    db.session.add(metodo)
    pedido.estado = "Confirmado"
    limpiar_carrito_y_sesion(current_user.id)
    db.session.commit()


def registrar_pago_pse(pedido, banco, tipo_persona, tipo_documento, numero_documento):
    """Registra el pago PSE."""
    metodo = MetodoPago(
        pedido_id=pedido.id,
        tipo_pago="pse",
        estado_pago="Aprobado",
        banco=banco,
        tipo_persona=tipo_persona,
        tipo_documento=tipo_documento,
        numero_documento=numero_documento[-4:],
    )
    db.session.add(metodo)
    pedido.estado = "Confirmado"
    limpiar_carrito_y_sesion(current_user.id)
    db.session.commit()

# Función para verificar el número de tarjeta con el algoritmo Luhn
def verificar_tarjeta_luhn(numero_tarjeta):
    """
    Verifica si el número de tarjeta es válido utilizando el algoritmo Luhn.
    """
    suma = 0
    longitud = len(numero_tarjeta)
    
    for i, digito in enumerate(numero_tarjeta):
        n = int(digito)
        
        # Si el índice es impar (empezando desde 0), duplicamos el valor
        if (longitud - i) % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
                
        suma += n

    return suma % 10 == 0