import csv
import io
from datetime import date
from decimal import Decimal

from flask import Blueprint, Response, abort, render_template, request
from flask_login import current_user
from sqlalchemy import func

from app import db
from app.models import Expense, Product, Sale, SaleItem, SalePayment
from app.timeutils import nigeria_date_range_to_utc, nigeria_today
from app.utils import role_required

bp = Blueprint("reports", __name__, url_prefix="/reports")


def _dates():
    today = nigeria_today()
    try:
        start_date = date.fromisoformat(request.args.get("start", today.isoformat()))
        end_date = date.fromisoformat(request.args.get("end", today.isoformat()))
        if end_date < start_date or (end_date - start_date).days > 366:
            raise ValueError
    except ValueError:
        abort(400, description="Choose valid report dates no more than 366 days apart.")
    start, end = nigeria_date_range_to_utc(start_date, end_date)
    return start_date, end_date, start, end


@bp.route("/")
@role_required("owner", "manager")
def index():
    start_date, end_date, start, end = _dates()
    sales = Sale.query.filter(
        Sale.business_id == current_user.business_id, Sale.created_at >= start, Sale.created_at < end,
    ).order_by(Sale.created_at.desc()).all()
    sale_ids = [sale.id for sale in sales]
    gross_sales = sum((sale.subtotal for sale in sales), Decimal("0.00"))
    discount = sum((sale.discount for sale in sales), Decimal("0.00"))
    net_sales = sum((sale.total for sale in sales), Decimal("0.00"))
    cogs = db.session.query(func.coalesce(func.sum(SaleItem.quantity * SaleItem.unit_cost), 0)).filter(
        SaleItem.business_id == current_user.business_id, SaleItem.sale_id.in_(sale_ids),
    ).scalar() if sale_ids else Decimal("0.00")
    expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.business_id == current_user.business_id, Expense.created_at >= start, Expense.created_at < end,
    ).scalar()
    payments = db.session.query(SalePayment.method, func.sum(SalePayment.amount)).filter(
        SalePayment.business_id == current_user.business_id, SalePayment.sale_id.in_(sale_ids),
    ).group_by(SalePayment.method).all() if sale_ids else []
    best_sellers = db.session.query(
        SaleItem.product_name, func.sum(SaleItem.quantity).label("units"), func.sum(SaleItem.line_total).label("revenue"),
    ).filter(
        SaleItem.business_id == current_user.business_id, SaleItem.sale_id.in_(sale_ids),
    ).group_by(SaleItem.product_name).order_by(func.sum(SaleItem.quantity).desc()).limit(10).all() if sale_ids else []
    stock_value = db.session.query(func.coalesce(func.sum(Product.qty * Product.buy_price), 0)).filter(
        Product.business_id == current_user.business_id, Product.archived.is_(False),
    ).scalar()
    return render_template(
        "reports.html", start_date=start_date, end_date=end_date,
        gross_sales=gross_sales, discount=discount, net_sales=net_sales, cogs=cogs or 0,
        gross_profit=net_sales - Decimal(str(cogs or 0)), expenses=expenses or 0,
        net_profit=net_sales - Decimal(str(cogs or 0)) - Decimal(str(expenses or 0)),
        payments=payments, best_sellers=best_sellers, stock_value=stock_value or 0,
        sales=sales,
    )


@bp.route("/sales.csv")
@role_required("owner", "manager")
def export_sales():
    _, _, start, end = _dates()
    sales = Sale.query.filter(
        Sale.business_id == current_user.business_id, Sale.created_at >= start, Sale.created_at < end,
    ).order_by(Sale.created_at.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["receipt", "date", "customer", "subtotal", "discount", "total", "cost_of_goods"])
    for sale in sales:
        cogs = sum((item.unit_cost * item.quantity for item in sale.items), Decimal("0.00"))
        customer_name = _safe_csv_text(sale.customer.name) if sale.customer else ""
        writer.writerow([sale.receipt_number, sale.created_at.isoformat() + "Z", customer_name, sale.subtotal, sale.discount, sale.total, cogs])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=sales-report.csv"})


def _safe_csv_text(value):
    text = str(value or "")
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text
