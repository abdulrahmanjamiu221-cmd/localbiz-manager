from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import CreditTransaction, Customer, Product, Sale, SaleItem, SalePayment
from app.services.inventory_service import adjust_stock

CENT = Decimal("0.01")
MAX_MONEY = Decimal("99999999.99")


class SaleError(ValueError):
    pass


def create_sale(user, cart_rows, discount, payments, customer_id=None, idempotency_key=None):
    business_id = user.business_id
    if not isinstance(payments, dict):
        raise SaleError("Payment details are invalid.")
    if not isinstance(idempotency_key, str) or not idempotency_key or len(idempotency_key) > 80:
        raise SaleError("Checkout idempotency key is invalid.")
    key = idempotency_key
    existing = Sale.query.filter_by(business_id=business_id, idempotency_key=key).first()
    if existing:
        return existing
    try:
        discount = Decimal(str(discount)).quantize(CENT)
    except (InvalidOperation, TypeError):
        raise SaleError("Enter a valid discount.")
    if not discount.is_finite():
        raise SaleError("Enter a valid discount.")
    if discount < 0:
        raise SaleError("Discount cannot be negative.")

    normalized = {}
    for row in cart_rows:
        try:
            product_id = int(row["product_id"])
            quantity = int(row["quantity"])
        except (KeyError, TypeError, ValueError):
            raise SaleError("The cart contains an invalid product or quantity.")
        if quantity < 1:
            raise SaleError("Quantity must be at least 1.")
        normalized[product_id] = normalized.get(product_id, 0) + quantity
    if not normalized:
        raise SaleError("Add at least one product to the sale.")

    product_ids = sorted(normalized)
    products = Product.query.filter(
        Product.business_id == business_id,
        Product.id.in_(product_ids),
        Product.archived.is_(False),
    ).order_by(Product.id).with_for_update().all()
    if len(products) != len(product_ids):
        raise SaleError("One or more products are unavailable.")

    subtotal = Decimal("0.00")
    snapshots = []
    for product in products:
        quantity = normalized[product.id]
        if product.qty < quantity:
            raise SaleError(f"Not enough stock for {product.name}.")
        price = Decimal(product.sell_price).quantize(CENT)
        cost = Decimal(product.buy_price).quantize(CENT)
        line_total = price * quantity
        subtotal += line_total
        snapshots.append((product, quantity, price, cost, line_total))
    subtotal = subtotal.quantize(CENT)
    if subtotal > MAX_MONEY:
        raise SaleError("Sale total exceeds the supported amount.")
    if discount > subtotal:
        raise SaleError("Discount cannot exceed the subtotal.")
    total = (subtotal - discount).quantize(CENT)

    payment_rows = []
    paid = Decimal("0.00")
    for method, amount in payments.items():
        if method not in {"cash", "transfer", "card"}:
            raise SaleError("Choose a valid payment method.")
        try:
            value = Decimal(str(amount or "0")).quantize(CENT)
        except (InvalidOperation, TypeError):
            raise SaleError("Enter a valid payment amount.")
        if not value.is_finite():
            raise SaleError("Enter a valid payment amount.")
        if value < 0:
            raise SaleError("Payment amounts cannot be negative.")
        if value:
            payment_rows.append((method, value))
            paid += value
    if paid > total:
        raise SaleError("Payments cannot exceed the sale total.")
    credit = (total - paid).quantize(CENT)
    customer = None
    if customer_id is not None:
        try:
            customer_id = int(customer_id)
        except (TypeError, ValueError):
            raise SaleError("Customer not found.")
    if credit:
        if not customer_id:
            raise SaleError("Select a customer for a credit sale.")
        customer = Customer.query.filter_by(id=customer_id, business_id=business_id).first()
        if customer is None:
            raise SaleError("Customer not found.")
    elif customer_id:
        customer = Customer.query.filter_by(id=customer_id, business_id=business_id).first()
        if customer is None:
            raise SaleError("Customer not found.")

    receipt = f"LB-{datetime.now(timezone.utc):%y%m%d}-{uuid4().hex[:8].upper()}"
    sale = Sale(
        business_id=business_id, user_id=user.id, customer_id=customer.id if customer else None,
        receipt_number=receipt, idempotency_key=key, subtotal=subtotal,
        discount=discount, total=total,
    )
    try:
        db.session.add(sale)
        db.session.flush()
        for product, quantity, price, cost, line_total in snapshots:
            adjust_stock(product, -quantity, user, f"Sale {receipt}", cost, commit=False)
            db.session.add(SaleItem(
                business_id=business_id, sale_id=sale.id, product_id=product.id,
                product_name=product.name, quantity=quantity, unit_price=price,
                unit_cost=cost, line_total=line_total,
            ))
        for method, amount in payment_rows:
            db.session.add(SalePayment(
                business_id=business_id, sale_id=sale.id, method=method, amount=amount,
            ))
        if credit:
            db.session.add(CreditTransaction(
                business_id=business_id, customer_id=customer.id, sale_id=sale.id,
                user_id=user.id, kind="charge", amount=credit, note=f"Sale {receipt}",
            ))
        db.session.commit()
        return sale
    except IntegrityError:
        db.session.rollback()
        existing = Sale.query.filter_by(business_id=business_id, idempotency_key=key).first()
        if existing:
            return existing
        raise SaleError("The sale could not be saved. Please try again.")
    except Exception:
        db.session.rollback()
        raise
