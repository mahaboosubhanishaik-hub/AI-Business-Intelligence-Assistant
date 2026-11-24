import threading

from flask import (
    Flask,
    render_template,
    redirect,
    request,
    url_for
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import IntegrityError

from config import Config


# ==========================================
# EXTENSIONS
# ==========================================

db = SQLAlchemy()

login_manager = LoginManager()

migrate = Migrate()
csrf = CSRFProtect()

limiter = Limiter(
    key_func=get_remote_address,
    # Avoid a global cap on normal page views. Routes can opt into specific
    # limits where they protect expensive or abuse-prone operations.
    default_limits=[],
    storage_uri="memory://"
)


# ==========================================
# APPLICATION FACTORY
# ==========================================

def create_app():

    app = Flask(__name__)

    # Load configuration
    app.config.from_object(Config)

    if app.config["IS_PRODUCTION"]:
        if not app.config["SECRET_KEY"]:
            raise RuntimeError("SECRET_KEY must be configured in production.")
        if (
            app.config["ADMIN_PASSWORD"] == "A12345678"
            or len(app.config["ADMIN_PASSWORD"]) < 12
        ):
            raise RuntimeError(
                "Set an ADMIN_PASSWORD of at least 12 characters in production; "
                "the development default is disabled."
            )
        if not app.config["SESSION_COOKIE_SECURE"]:
            raise RuntimeError("SESSION_COOKIE_SECURE must be enabled in production.")


    # ======================================
    # INITIALIZE EXTENSIONS
    # ======================================

    db.init_app(app)

    login_manager.init_app(app)

    csrf.init_app(app)

    migrate.init_app(
        app,
        db
    )

    limiter.init_app(app)


    # ======================================
    # LOGIN CONFIGURATION
    # ======================================

    login_manager.login_view = "auth.login"


    # ======================================
    # IMPORT MODELS
    # ======================================

    from app.models.user import User
    from app.models.dataset import Dataset
    from app.models.quality_audit import QualityAudit
    from app.models.activity_log import ActivityLog
    from app.models.monthly_budget import MonthlyBudget


    # ======================================
    # USER LOADER
    # ======================================

    @login_manager.user_loader
    def load_user(user_id):
        user = db.session.get(
            User,
            int(user_id)
        )
        return user if user and user.active else None


    # ======================================
    # DEFAULT ADMIN PROVISIONING
    # ======================================

    admin_seed_lock = threading.Lock()
    app.extensions["default_admin_seeded"] = False

    @app.before_request
    def ensure_default_admin():
        if app.extensions["default_admin_seeded"]:
            return

        with admin_seed_lock:
            if app.extensions["default_admin_seeded"]:
                return

            username = app.config["ADMIN_USERNAME"].strip().lower()
            admin = User.query.filter_by(role="admin").first()

            if admin is None:
                configured_account = User.query.filter_by(username=username).first()
                if configured_account is not None:
                    raise RuntimeError(
                        "The configured ADMIN_USERNAME belongs to a non-admin account. "
                        "Choose a different ADMIN_USERNAME; accounts are never promoted automatically."
                    )

                admin = User.query.filter_by(
                    email=app.config["ADMIN_EMAIL"].strip().lower()
                ).first()
                if admin is not None:
                    raise RuntimeError(
                        "ADMIN_EMAIL is already used by another account. "
                        "Set a unique ADMIN_EMAIL before starting the application."
                    )

                admin = User(
                    name="Administrator",
                    username=username,
                    email=app.config["ADMIN_EMAIL"].strip().lower(),
                    role="admin",
                    active=True
                )
                admin.set_password(app.config["ADMIN_PASSWORD"])
                db.session.add(admin)

                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    admin = User.query.filter_by(username=username).first()
                    if admin is None or not admin.is_admin:
                        raise

            app.extensions["default_admin_seeded"] = True

    @app.before_request
    def require_temporary_password_change():
        if (
            current_user.is_authenticated
            and not current_user.is_admin
            and current_user.must_change_password
            and request.endpoint not in {
                "auth.change_password",
                "auth.logout",
                "static"
            }
        ):
            return redirect(url_for("auth.change_password"))


    # ======================================
    # SECURITY HTTP HEADERS MIDDLEWARE
    # ======================================

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


    # ======================================
    # ERROR HANDLERS
    # ======================================

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("500.html"), 500


    # ======================================
    # REGISTER BLUEPRINTS
    # ======================================

    from app.routes import main
    app.register_blueprint(main)

    from app.routes.auth import auth
    app.register_blueprint(auth)

    from app.routes.data import data
    app.register_blueprint(data)

    from app.routes.analytics import analytics
    app.register_blueprint(analytics)

    from app.routes.ai import ai
    app.register_blueprint(ai)

    from app.routes.admin import admin
    app.register_blueprint(admin)

    from app.routes.reports import reports
    app.register_blueprint(reports)


    return app
