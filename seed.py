import os
import sys

from app import create_app, db
from app.models import Business, Role, User


def seed_admin():
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email and not password:
        print("ADMIN_EMAIL and ADMIN_PASSWORD are not set; no admin account was created.")
        return
    if not email or len(password) < 12:
        raise ValueError("Set ADMIN_EMAIL and an ADMIN_PASSWORD of at least 12 characters.")
    if User.query.filter_by(email=email).first():
        print(f"An account for {email} already exists; no changes made.")
        return
    business = Business(name=os.getenv("ADMIN_BUSINESS_NAME", "LocalBiz Admin"))
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
        name="Administrator", email=email,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print(f"Seeded administrator account for {email}.")


if __name__ == "__main__":
    application = create_app()
    with application.app_context():
        try:
            seed_admin()
        except Exception as error:
            db.session.rollback()
            print(f"Admin seed failed: {error}", file=sys.stderr)
            raise
