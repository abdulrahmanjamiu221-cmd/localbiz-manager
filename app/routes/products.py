import csv
import io
from decimal import Decimal, InvalidOperation

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.forms import ProductForm
from app.models import Category, Product
from app.services.inventory_service import InventoryError, adjust_stock
from app.utils import role_required

bp = Blueprint("products", __name__, url_prefix="/products")


@bp.route("/")
@role_required("owner", "manager", "cashier")
def index():
    search = request.args.get("q", "").strip()
    query = Product.query.filter_by(business_id=current_user.business_id, archived=False)
    if search:
        query = query.filter(db.or_(Product.name.ilike(f"%{search}%"), Product.sku.ilike(f"%{search}%")))
    products = query.order_by(Product.name).all()
    return render_template("products.html", products=products, search=search)


@bp.route("/new", methods=["GET", "POST"])
@role_required("owner", "manager")
def create():
    form = ProductForm()
    if form.validate_on_submit():
        category = _category(form.category.data)
        product = Product(
            business_id=current_user.business_id, category_id=category.id if category else None,
            sku=form.sku.data.strip(), name=form.name.data.strip(),
            buy_price=form.buy_price.data, sell_price=form.sell_price.data,
            qty=0, low_stock_threshold=form.low_stock_threshold.data,
        )
        try:
            db.session.add(product)
            db.session.flush()
            opening = form.qty.data
            if opening:
                adjust_stock(product, opening, current_user, "Opening stock", form.buy_price.data, commit=False)
            db.session.commit()
            flash("Product added.", "success")
            return redirect(url_for("products.index"))
        except IntegrityError:
            db.session.rollback()
            flash("That SKU is already in use in your business.", "danger")
        except InventoryError as error:
            db.session.rollback()
            flash(str(error), "danger")
    return render_template("product_form.html", form=form, title="Add product")


@bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@role_required("owner", "manager")
def edit(product_id):
    product = Product.query.filter_by(id=product_id, business_id=current_user.business_id).first_or_404()
    form = ProductForm(obj=product)
    if request.method == "GET":
        form.category.data = product.category.name if product.category else ""
    if form.validate_on_submit():
        category = _category(form.category.data)
        old_qty = product.qty
        product.name = form.name.data.strip()
        product.sku = form.sku.data.strip()
        product.buy_price = form.buy_price.data
        product.sell_price = form.sell_price.data
        product.low_stock_threshold = form.low_stock_threshold.data
        product.category_id = category.id if category else None
        try:
            db.session.flush()
            change = form.qty.data - old_qty
            if change:
                adjust_stock(product, change, current_user, "Stock adjustment", form.buy_price.data, commit=False)
            db.session.commit()
            flash("Product updated.", "success")
            return redirect(url_for("products.index"))
        except IntegrityError:
            db.session.rollback()
            flash("That SKU is already in use in your business.", "danger")
        except InventoryError as error:
            db.session.rollback()
            flash(str(error), "danger")
    return render_template("product_form.html", form=form, title="Edit product")


@bp.route("/<int:product_id>/archive", methods=["POST"])
@role_required("owner", "manager")
def archive(product_id):
    product = Product.query.filter_by(id=product_id, business_id=current_user.business_id).first_or_404()
    product.archived = True
    db.session.commit()
    flash("Product archived; historical sales are unchanged.", "info")
    return redirect(url_for("products.index"))


@bp.route("/export.csv")
@role_required("owner", "manager")
def export_csv():
    rows = Product.query.filter_by(business_id=current_user.business_id).order_by(Product.name).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["sku", "name", "buy_price", "sell_price", "qty", "low_stock_threshold", "archived"])
    for product in rows:
        writer.writerow([_safe_csv_text(product.sku), _safe_csv_text(product.name), product.buy_price, product.sell_price, product.qty, product.low_stock_threshold, product.archived])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=products.csv"})


@bp.route("/import", methods=["POST"])
@role_required("owner", "manager")
def import_csv():
    upload = request.files.get("file")
    if not upload or not upload.filename.lower().endswith(".csv"):
        flash("Choose a CSV file to import.", "danger")
        return redirect(url_for("products.index"))
    try:
        reader = csv.DictReader(io.StringIO(upload.stream.read().decode("utf-8-sig")))
        required = {"sku", "name", "buy_price", "sell_price", "qty", "low_stock_threshold"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("CSV must include sku, name, buy_price, sell_price, qty and low_stock_threshold columns.")
        imported = 0
        for row in reader:
            sku = row["sku"].strip()
            product = Product.query.filter_by(business_id=current_user.business_id, sku=sku).first()
            if product is None:
                product = Product(business_id=current_user.business_id, sku=sku, name=row["name"].strip(), qty=0)
                db.session.add(product)
                db.session.flush()
            change = int(row["qty"]) - product.qty
            product.name = row["name"].strip()
            product.buy_price = Decimal(row["buy_price"]).quantize(Decimal("0.01"))
            product.sell_price = Decimal(row["sell_price"]).quantize(Decimal("0.01"))
            product.low_stock_threshold = int(row["low_stock_threshold"])
            product.archived = False
            if change:
                adjust_stock(product, change, current_user, "CSV stock import", product.buy_price, commit=False)
            imported += 1
        db.session.commit()
        flash(f"Imported {imported} product row(s).", "success")
    except (ValueError, KeyError, InvalidOperation, UnicodeDecodeError, IntegrityError, InventoryError) as error:
        db.session.rollback()
        flash(f"Import failed: {error}", "danger")
    return redirect(url_for("products.index"))


def _category(name):
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    category = Category.query.filter_by(business_id=current_user.business_id, name=cleaned).first()
    if category is None:
        category = Category(business_id=current_user.business_id, name=cleaned)
        db.session.add(category)
        db.session.flush()
    return category


def _safe_csv_text(value):
    text = str(value or "")
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text
