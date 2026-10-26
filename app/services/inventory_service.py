from sqlalchemy import update

from app import db
from app.models import Product, StockMovement


class InventoryError(ValueError):
    pass


def adjust_stock(product, quantity_change, user, reason, unit_cost=None, commit=True):
    if product.business_id != user.business_id:
        raise InventoryError("Product not found.")
    result = db.session.execute(
        update(Product)
        .where(
            Product.id == product.id,
            Product.business_id == user.business_id,
            Product.qty + quantity_change >= 0,
        )
        .values(qty=Product.qty + quantity_change)
    )
    if result.rowcount != 1:
        raise InventoryError("Insufficient stock or product no longer exists.")
    movement = StockMovement(
        business_id=user.business_id,
        product_id=product.id,
        user_id=user.id,
        reason=reason,
        quantity_change=quantity_change,
        unit_cost=unit_cost if unit_cost is not None else product.buy_price,
    )
    db.session.add(movement)
    if commit:
        db.session.commit()
    return movement
