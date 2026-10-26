from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from app import db, limiter
from app.forms import LoginForm, RegisterForm
from app.models import Business, Role, User

bp = Blueprint("auth", __name__)


@bp.route("/")
def index():
    return redirect(url_for("dashboard.index") if current_user.is_authenticated else url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user is None or not user.active or not user.check_password(form.password.data):
            flash("Email or password is incorrect.", "danger")
        else:
            login_user(user, remember=form.remember.data, fresh=True)
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//") and "\\" not in next_url:
                return redirect(next_url)
            return redirect(url_for("dashboard.index"))
    return render_template("login.html", form=form)


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("3 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = RegisterForm()
    if form.validate_on_submit():
        business = Business(name=form.business_name.data.strip(), phone=form.phone.data.strip() or None)
        db.session.add(business)
        db.session.flush()
        roles = {}
        for name, permissions in (
            ("owner", ["all"]), ("manager", ["sales", "inventory", "customers", "expenses", "reports"]),
            ("cashier", ["sales", "customers"]),
        ):
            role = Role(business_id=business.id, name=name, permissions=permissions)
            db.session.add(role)
            roles[name] = role
        db.session.flush()
        user = User(
            business_id=business.id, role_id=roles["owner"].id,
            name=form.owner_name.data.strip(), email=form.email.data.strip().lower(),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("An account with that email already exists.", "danger")
            return render_template("register.html", form=form)
        login_user(user, fresh=True)
        flash("Your business workspace is ready.", "success")
        return redirect(url_for("dashboard.index"))
    return render_template("register.html", form=form)


@bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
