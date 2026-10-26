from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user

from app import db
from app.forms import ExpenseForm
from app.models import Expense
from app.utils import role_required

bp = Blueprint("expenses", __name__, url_prefix="/expenses")


@bp.route("/", methods=["GET", "POST"])
@role_required("owner", "manager")
def index():
    form = ExpenseForm()
    if form.validate_on_submit():
        db.session.add(Expense(
            business_id=current_user.business_id, user_id=current_user.id,
            title=form.title.data.strip(), category=form.category.data.strip(),
            amount=form.amount.data, note=form.note.data.strip() or None,
        ))
        db.session.commit()
        flash("Expense recorded.", "success")
        return redirect(url_for("expenses.index"))
    expenses = Expense.query.filter_by(business_id=current_user.business_id).order_by(Expense.created_at.desc()).limit(100).all()
    return render_template("expenses.html", form=form, expenses=expenses)
