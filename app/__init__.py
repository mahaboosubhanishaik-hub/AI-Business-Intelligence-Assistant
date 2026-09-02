from flask import (
    Flask,
    render_template
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config


# ==========================================
# EXTENSIONS
# ==========================================

db = SQLAlchemy()

login_manager = LoginManager()

migrate = Migrate()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)


# ==========================================
# APPLICATION FACTORY
# ==========================================

def create_app():

    app = Flask(__name__)

    # Load configuration
    app.config.from_object(Config)


    # ======================================
    # INITIALIZE EXTENSIONS
    # ======================================

    db.init_app(app)

    login_manager.init_app(app)

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


    # ======================================
    # USER LOADER
    # ======================================

    @login_manager.user_loader
    def load_user(user_id):

        return db.session.get(
            User,
            int(user_id)
        )


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


    return app