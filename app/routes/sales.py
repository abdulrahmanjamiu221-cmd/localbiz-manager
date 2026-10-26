from decimal import Decimal

from flask import Blueprint, jsonify, render_template, request, url_for
from flask_login import current_user

from app.models import Customer, Product, Sale
from app.services.sales_service import SaleError, create_sale
from app.utils import role_required

bp = Blueprint("sales", __name__, url_prefix="/sales")


@bp.route("/pos")
@role_required("owner", "manager", "cashier")
def pos():
    products = Product.query.filter_by(business_id=current_user.business_id, archived=False).order_by(Product.name).all()
    customers = Customer.query.filter_by(business_id=current_user.business_id).order_by(Customer.name).all()
    return render_template("pos.html", products=products, customers=customers)


@bp.route("/checkout", methods=["POST"])
@role_required("owner", "manager", "cashier")
def checkout():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Invalid checkout request."), 400
    payments = data.get("payments") or {}
    if not isinstance(payments, dict):
        return jsonify(error="Payment details are invalid."), 400
    try:
        sale = create_sale(
            current_user, data.get("items") or [], data.get("discount", "0"),
            payments, data.get("customer_id"), data.get("idempotency_key"),
        )
    except SaleError as error:
        return jsonify(error=str(error)), 400
    return jsonify(redirect=url_for("sales.receipt", sale_id=sale.id))


@bp.route("/")
@role_required("owner", "manager", "cashier")
def index():
    sales = Sale.query.filter_by(business_id=current_user.business_id).order_by(Sale.created_at.desc()).limit(100).all()
    return render_template("sales.html", sales=sales)


@bp.route("/<int:sale_id>/receipt")
@role_required("owner", "manager", "cashier")
def receipt(sale_id):
    sale = Sale.query.filter_by(id=sale_id, business_id=current_user.business_id).first_or_404()
    paid = sum((payment.amount for payment in sale.payments), Decimal("0.00"))
    return render_template("receipt.html", sale=sale, paid=paid, balance=sale.total - paid)
