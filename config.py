import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300
    }
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    IS_PRODUCTION = (
        os.getenv("RENDER", "").lower() == "true"
        or os.getenv("FLASK_ENV", "").lower() == "production"
    )
    ADMIN_USERNAME = (os.getenv("ADMIN_USERNAME") or "@admin").strip().lower()
    ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "admin@localhost").strip().lower()
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or "A12345678"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv(
        "SESSION_COOKIE_SECURE",
        "true" if IS_PRODUCTION else "false"
    ).lower() in ("1", "true", "yes")
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    WTF_CSRF_TIME_LIMIT = 3600
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() in ("1", "true", "yes")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "no-reply@localhost")