from decimal import Decimal

import bcrypt
import hashlib
from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint

from app import db
from app.timeutils import utcnow


class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    phone = db.Column(db.String(30))
    address = db.Column(db.String(240))
    currency = db.Column(db.String(3), nullable=False, default="NGN")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(30), nullable=False)
    permissions = db.Column(db.JSON, nullable=False, default=list)
    __table_args__ = (UniqueConstraint("business_id", "name"),)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey("role.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    password_hash = db.Column(db.String(100), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("email"),)
    business = db.relationship("Business", lazy="joined")
    role = db.relationship("Role", lazy="joined")

    def set_password(self, password):
        digest = hashlib.sha256(password.encode("utf-8")).hexdigest().encode("ascii")
        self.password_hash = bcrypt.hashpw(digest, bcrypt.gensalt()).decode("utf-8")

    def check_password(self, password):
        try:
            digest = hashlib.sha256(password.encode("utf-8")).hexdigest().encode("ascii")
            return bcrypt.checkpw(digest, self.password_hash.encode("utf-8"))
        except ValueError:
            return False

    @property
    def is_active(self):
        return self.active


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    __table_args__ = (UniqueConstraint("business_id", "name"),)


class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(255))
    address = db.Column(db.String(240))
    archived = db.Column(db.Boolean, nullable=False, default=False)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=True)
    sku = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    buy_price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    sell_price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    qty = db.Column(db.Integer, nullable=False, default=0)
    low_stock_threshold = db.Column(db.Integer, nullable=False, default=5)
    archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    category = db.relationship("Category")
    supplier = db.relationship("Supplier")
    __table_args__ = (
        UniqueConstraint("business_id", "sku"),
        CheckConstraint("qty >= 0", name="ck_product_nonnegative_qty"),
        CheckConstraint("buy_price >= 0 AND sell_price >= 0", name="ck_product_nonnegative_prices"),
    )


class StockMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.String(160), nullable=False)
    quantity_change = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    product = db.relationship("Product")
    user = db.relationship("User")


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(255))
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True)
    receipt_number = db.Column(db.String(40), nullable=False)
    idempotency_key = db.Column(db.String(80), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    discount = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    total = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    customer = db.relationship("Customer")
    user = db.relationship("User")
    items = db.relationship("SaleItem", cascade="all, delete-orphan", lazy="selectin")
    payments = db.relationship("SalePayment", cascade="all, delete-orphan", lazy="selectin")
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key"),
        UniqueConstraint("business_id", "receipt_number"),
        CheckConstraint("total >= 0 AND discount >= 0", name="ck_sale_nonnegative_totals"),
    )


class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product_name = db.Column(db.String(160), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    unit_cost = db.Column(db.Numeric(10, 2), nullable=False)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)
    product = db.relationship("Product")


class SalePayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id", ondelete="CASCADE"), nullable=False, index=True)
    method = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    __table_args__ = (CheckConstraint("amount > 0", name="ck_sale_payment_positive"),)


class CreditTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False, index=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    method = db.Column(db.String(20))
    note = db.Column(db.String(240))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    customer = db.relationship("Customer")
    user = db.relationship("User")


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="General")
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    user = db.relationship("User")
