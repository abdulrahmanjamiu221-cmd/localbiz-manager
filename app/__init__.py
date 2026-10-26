import os
from datetime import timezone
from decimal import Decimal

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from zoneinfo import ZoneInfo

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address, default_limits=[])


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if not database_url:
        os.makedirs(app.instance_path, exist_ok=True)
        database_url = "sqlite:///" + os.path.join(app.instance_path, "localbiz.sqlite").replace("\\", "/")

    app.config.update(
        SECRET_KEY=os.getenv("JWT_SECRET", "local-only-change-me"),
        SUPABASE_URL=os.getenv("SUPABASE_URL", ""),
        SUPABASE_ANON_KEY=os.getenv("SUPABASE_ANON_KEY", ""),
        APP_ENV=os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True} if database_url.startswith("postgresql") else {},
        WTF_CSRF_TIME_LIMIT=3600,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        RATELIMIT_STORAGE_URI=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
    )
    if test_config:
        app.config.update(test_config)
    if app.config["SECRET_KEY"] == "local-only-change-me" and not app.testing:
        app.logger.warning("JWT_SECRET is not configured; set a unique secret before deployment.")
    if app.config["APP_ENV"].lower() == "production":
        if not app.config["SECRET_KEY"] or app.config["SECRET_KEY"] == "local-only-change-me" or len(app.config["SECRET_KEY"]) < 32:
            raise RuntimeError("Set a random JWT_SECRET of at least 32 characters before running in production.")
        if not database_url.startswith("postgresql"):
            raise RuntimeError("Set DATABASE_URL to the Supabase PostgreSQL connection string in production.")
        if not app.config["SESSION_COOKIE_SECURE"]:
            raise RuntimeError("Set COOKIE_SECURE=true when running behind HTTPS in production.")

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    from app import models  # noqa: F401
    from app.routes.auth import bp as auth_bp
    from app.routes.customers import bp as customers_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.expenses import bp as expenses_bp
    from app.routes.products import bp as products_bp
    from app.routes.reports import bp as reports_bp
    from app.routes.sales import bp as sales_bp
    from app.routes.settings import bp as settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)

    @app.template_filter("naira")
    def naira(value):
        return "₦{:,.2f}".format(Decimal(str(value or 0)))

    @app.template_filter("nigeria_time")
    def nigeria_time(value):
        if value is None:
            return ""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(ZoneInfo("Africa/Lagos")).strftime("%d %b %Y, %H:%M")

    @app.context_processor
    def inject_business():
        from flask_login import current_user
        return {"business": current_user.business if current_user.is_authenticated else None}

    return app


@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return db.session.get(User, int(user_id))
