from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import case, func

from app import db
from app.forms import CustomerForm
from app.models import CreditTransaction, Customer
from app.utils import role_required

bp = Blueprint("customers", __name__, url_prefix="/customers")


def customer_balance(customer_id):
    return db.session.query(func.coalesce(func.sum(
        case((CreditTransaction.kind == "charge", CreditTransaction.amount), else_=-CreditTransaction.amount)
    ), 0)).filter(
        CreditTransaction.business_id == current_user.business_id,
        CreditTransaction.customer_id == customer_id,
    ).scalar() or Decimal("0.00")


@bp.route("/")
@role_required("owner", "manager", "cashier")
def index():
    customers = Customer.query.filter_by(business_id=current_user.business_id).order_by(Customer.name).all()
    balances = {customer.id: customer_balance(customer.id) for customer in customers}
    return render_template("customers.html", customers=customers, balances=balances)


@bp.route("/new", methods=["GET", "POST"])
@role_required("owner", "manager", "cashier")
def create():
    form = CustomerForm()
    if form.validate_on_submit():
        customer = Customer(
            business_id=current_user.business_id, name=form.name.data.strip(),
            phone=form.phone.data.strip() or None, email=(form.email.data or "").strip().lower() or None,
            notes=form.notes.data.strip() or None,
        )
        db.session.add(customer)
        db.session.commit()
        flash("Customer added.", "success")
        return redirect(url_for("customers.index"))
    return render_template("customer_form.html", form=form, title="Add customer")


@bp.route("/<int:customer_id>")
@role_required("owner", "manager", "cashier")
def detail(customer_id):
    customer = Customer.query.filter_by(id=customer_id, business_id=current_user.business_id).first_or_404()
    transactions = CreditTransaction.query.filter_by(
        business_id=current_user.business_id, customer_id=customer.id,
    ).order_by(CreditTransaction.created_at.desc()).all()
    return render_template("customer_detail.html", customer=customer, transactions=transactions, balance=customer_balance(customer.id))


@bp.route("/<int:customer_id>/repay", methods=["POST"])
@role_required("owner", "manager", "cashier")
def repay(customer_id):
    customer = Customer.query.filter_by(id=customer_id, business_id=current_user.business_id).first_or_404()
    try:
        amount = Decimal(request.form.get("amount", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        flash("Enter a valid repayment amount.", "danger")
        return redirect(url_for("customers.detail", customer_id=customer.id))
    method = request.form.get("method", "")
    balance = Decimal(str(customer_balance(customer.id)))
    if not amount.is_finite() or amount <= 0 or amount > balance or method not in {"cash", "transfer", "card"}:
        flash("Repayment must be positive, no greater than the balance, and use a valid method.", "danger")
        return redirect(url_for("customers.detail", customer_id=customer.id))
    db.session.add(CreditTransaction(
        business_id=current_user.business_id, customer_id=customer.id,
        user_id=current_user.id, kind="repayment", amount=amount,
        method=method, note=(request.form.get("note") or "")[:240] or None,
    ))
    db.session.commit()
    flash("Repayment recorded.", "success")
    return redirect(url_for("customers.detail", customer_id=customer.id))
