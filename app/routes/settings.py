from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.forms import BusinessForm, StaffForm
from app.models import Role, User
from app.utils import role_required

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/", methods=["GET", "POST"])
@role_required("owner")
def index():
    form = BusinessForm(obj=current_user.business)
    if form.validate_on_submit():
        current_user.business.name = form.name.data.strip()
        current_user.business.phone = form.phone.data.strip() or None
        current_user.business.address = form.address.data.strip() or None
        db.session.commit()
        flash("Business settings saved.", "success")
        return redirect(url_for("settings.index"))
    staff = User.query.filter_by(business_id=current_user.business_id).order_by(User.name).all()
    return render_template("settings.html", form=form, staff=staff)


@bp.route("/staff", methods=["POST"])
@role_required("owner")
def add_staff():
    form = StaffForm()
    if not form.validate_on_submit():
        flash("Check the staff details and try again.", "danger")
        return redirect(url_for("settings.index"))
    role = Role.query.filter_by(business_id=current_user.business_id, name=form.role.data).first()
    if role is None:
        flash("That staff role is not configured for this business.", "danger")
        return redirect(url_for("settings.index"))
    user = User(
        business_id=current_user.business_id, role_id=role.id,
        name=form.name.data.strip(), email=form.email.data.strip().lower(),
    )
    user.set_password(form.password.data)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("An account with that email already exists.", "danger")
        return redirect(url_for("settings.index"))
    flash("Staff member added.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/staff/<int:user_id>/toggle", methods=["POST"])
@role_required("owner")
def toggle_staff(user_id):
    staff = User.query.filter_by(id=user_id, business_id=current_user.business_id).first_or_404()
    if staff.id == current_user.id:
        flash("You cannot deactivate your own account.", "danger")
    elif staff.role.name == "owner":
        flash("The business owner account cannot be deactivated here.", "danger")
    else:
        staff.active = not staff.active
        db.session.commit()
        flash("Staff account status updated.", "success")
    return redirect(url_for("settings.index"))
