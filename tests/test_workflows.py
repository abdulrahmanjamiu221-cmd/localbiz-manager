import pytest

from decimal import Decimal

from app import db
from app.models import Business, Customer, Product, Role, Sale, SaleItem, User
from app.services.sales_service import SaleError, create_sale


def make_business(name, email):
    business = Business(name=name)
    db.session.add(business)
    db.session.flush()
    role = Role(business_id=business.id, name="owner", permissions=["all"])
    db.session.add(role)
    db.session.flush()
    user = User(business_id=business.id, role_id=role.id, name="Owner", email=email)
    user.set_password("correct-horse-battery")
    db.session.add(user)
    db.session.flush()
    return business, user


def test_business_registration_creates_isolated_roles(app, client):
    response = client.post("/register", data={
        "business_name": "Corner Shop",
        "owner_name": "Ada Owner",
        "email": "ada@example.com",
        "phone": "08000000000",
        "password": "a-long-test-password",
        "confirm": "a-long-test-password",
    })
    assert response.status_code == 302
    with app.app_context():
        business = Business.query.filter_by(name="Corner Shop").one()
        assert {role.name for role in Role.query.filter_by(business_id=business.id)} == {"owner", "manager", "cashier"}
        owner = User.query.filter_by(email="ada@example.com").one()
        assert owner.business_id == business.id
        assert owner.password_hash != "a-long-test-password"
        assert owner.check_password("a-long-test-password")


def test_sale_records_cost_snapshot_and_idempotently_deducts_stock(app):
    with app.app_context():
        business, owner = make_business("Shop One", "one@example.com")
        product = Product(
            business_id=business.id, sku="ITEM-1", name="Milk",
            buy_price=Decimal("800.00"), sell_price=Decimal("1200.00"), qty=5,
        )
        db.session.add(product)
        db.session.commit()

        checkout = {
            "product_id": product.id,
            "quantity": 2,
        }
        first = create_sale(owner, [checkout], "100", {"cash": "2300"}, idempotency_key="stable-key")
        duplicate = create_sale(owner, [checkout], "100", {"cash": "2300"}, idempotency_key="stable-key")
        assert first.id == duplicate.id
        db.session.refresh(product)
        assert product.qty == 3
        assert first.subtotal == Decimal("2400.00")
        assert first.discount == Decimal("100.00")
        assert first.total == Decimal("2300.00")
        assert first.items[0].unit_price == Decimal("1200.00")
        assert first.items[0].unit_cost == Decimal("800.00")

        product.buy_price = Decimal("950.00")
        product.sell_price = Decimal("1400.00")
        db.session.commit()
        db.session.refresh(first.items[0])
        assert first.items[0].unit_cost == Decimal("800.00")
        assert first.items[0].unit_price == Decimal("1200.00")
        assert Sale.query.filter_by(business_id=business.id).count() == 1


def test_credit_sale_is_scoped_and_tracks_customer_balance(app):
    with app.app_context():
        business, owner = make_business("Credit Shop", "credit@example.com")
        customer = Customer(business_id=business.id, name="Customer")
        product = Product(
            business_id=business.id, sku="PHONE-1", name="Cable",
            buy_price=Decimal("500.00"), sell_price=Decimal("1000.00"), qty=4,
        )
        db.session.add_all([customer, product])
        db.session.commit()

        sale = create_sale(
            owner, [{"product_id": product.id, "quantity": 2}], "0",
            {"cash": "500"}, customer_id=customer.id, idempotency_key="credit-key",
        )
        assert sale.total == Decimal("2000.00")
        assert sale.customer_id == customer.id
        assert sale.items[0].unit_cost == Decimal("500.00")
        assert sale.business_id == business.id
        assert Sale.query.filter_by(business_id=business.id).count() == 1
        assert product.qty == 2


def test_user_cannot_access_another_business_product(app, client):
    with app.app_context():
        first_business, first_owner = make_business("First", "first@example.com")
        second_business, _ = make_business("Second", "second@example.com")
        foreign_product = Product(
            business_id=second_business.id, sku="FOREIGN", name="Private product",
            buy_price=Decimal("1.00"), sell_price=Decimal("2.00"), qty=1,
        )
        db.session.add(foreign_product)
        db.session.commit()
        product_id = foreign_product.id
        email = first_owner.email

    response = client.post("/login", data={"email": email, "password": "correct-horse-battery"})
    assert response.status_code == 302
    response = client.get(f"/products/{product_id}/edit")
    assert response.status_code == 404


def test_owner_pages_render(app, client):
    response = client.post("/register", data={
        "business_name": "Route Shop",
        "owner_name": "Route Owner",
        "email": "routes@example.com",
        "phone": "",
        "password": "a-long-test-password",
        "confirm": "a-long-test-password",
    })
    assert response.status_code == 302
    for path in (
        "/dashboard", "/products/", "/products/new", "/sales/pos", "/sales/",
        "/customers/", "/customers/new", "/expenses/", "/reports/", "/settings/",
    ):
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"


def test_checkout_rejects_nonfinite_values_without_changing_stock(app):
    with app.app_context():
        business, owner = make_business("Validation Shop", "validation@example.com")
        product = Product(
            business_id=business.id, sku="VALID-1", name="Soap",
            buy_price=Decimal("10.00"), sell_price=Decimal("20.00"), qty=3,
        )
        db.session.add(product)
        db.session.commit()

        with pytest.raises(SaleError, match="idempotency key"):
            create_sale(owner, [{"product_id": product.id, "quantity": 1}], "0", {"cash": "20"})
        with pytest.raises(SaleError):
            create_sale(owner, [{"product_id": product.id, "quantity": 1}], "NaN", {"cash": "20"})
        with pytest.raises(SaleError):
            create_sale(owner, [{"product_id": product.id, "quantity": 1}], "0", {"cash": "Infinity"})
        db.session.refresh(product)
        assert product.qty == 3
        assert Sale.query.filter_by(business_id=business.id).count() == 0
