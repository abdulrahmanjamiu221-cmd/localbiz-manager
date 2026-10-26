from decimal import Decimal

from flask import Blueprint, render_template
from flask_login import current_user, login_required
from sqlalchemy import case, func

from app import db
from app.models import CreditTransaction, Expense, Product, Sale, SaleItem, SalePayment
from app.timeutils import nigeria_date_range_to_utc, nigeria_today

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def index():
    today = nigeria_today()
    start, end = nigeria_date_range_to_utc(today, today)
    sales = Sale.query.filter(
        Sale.business_id == current_user.business_id, Sale.created_at >= start, Sale.created_at < end,
    ).all()
    sale_ids = [s.id for s in sales]
    gross_sales = sum((s.total for s in sales), Decimal("0.00"))
    gross_cost = db.session.query(func.coalesce(func.sum(SaleItem.quantity * SaleItem.unit_cost), 0)).filter(
        SaleItem.business_id == current_user.business_id, SaleItem.sale_id.in_(sale_ids),
    ).scalar() if sale_ids else Decimal("0.00")
    expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.business_id == current_user.business_id,
        Expense.created_at >= start, Expense.created_at < end,
    ).scalar()
    payment_totals = dict(db.session.query(SalePayment.method, func.sum(SalePayment.amount)).filter(
        SalePayment.business_id == current_user.business_id, SalePayment.sale_id.in_(sale_ids),
    ).group_by(SalePayment.method).all()) if sale_ids else {}
    low_stock = Product.query.filter(
        Product.business_id == current_user.business_id,
        Product.archived.is_(False),
        Product.qty <= Product.low_stock_threshold,
    ).order_by(Product.qty.asc()).limit(8).all()

    balances = db.session.query(
        CreditTransaction.customer_id,
        func.sum(case((CreditTransaction.kind == "charge", CreditTransaction.amount), else_=-CreditTransaction.amount)).label("balance"),
    ).filter(CreditTransaction.business_id == current_user.business_id).group_by(
        CreditTransaction.customer_id
    ).having(func.sum(case((CreditTransaction.kind == "charge", CreditTransaction.amount), else_=-CreditTransaction.amount)) > 0).order_by(
        func.sum(case((CreditTransaction.kind == "charge", CreditTransaction.amount), else_=-CreditTransaction.amount)).desc()
    ).limit(5).all()
    from app.models import Customer
    debtors = [
        (Customer.query.filter_by(id=customer_id, business_id=current_user.business_id).first(), balance)
        for customer_id, balance in balances
    ]
    debtors = [(customer, balance) for customer, balance in debtors if customer]
    return render_template(
        "dashboard.html", gross_sales=gross_sales, gross_cost=gross_cost,
        expenses=expenses or Decimal("0.00"),
        net_profit=gross_sales - Decimal(str(gross_cost or 0)) - Decimal(str(expenses or 0)),
        payment_totals=payment_totals, low_stock=low_stock, debtors=debtors,
        sale_count=len(sales),
    )
