from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

from app import db


class User(UserMixin, db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    username = db.Column(
        db.String(40),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: f"user-{secrets.token_hex(8)}"
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        nullable=False,
        default="user",
        server_default="user"
    )

    active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default=db.true()
    )

    must_change_password = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false()
    )

    temporary_password_expires_at = db.Column(
        db.DateTime,
        nullable=True
    )

    temporary_password_used_at = db.Column(
        db.DateTime,
        nullable=True
    )

    failed_login_attempts = db.Column(
        db.Integer,
        nullable=False,
        default=0,
        server_default="0"
    )

    login_locked_until = db.Column(
        db.DateTime,
        nullable=True
    )

    @property
    def is_active(self):
        return self.active

    @property
    def is_admin(self):
        return self.role == "admin"

    def set_password(self, password):

        self.password_hash = generate_password_hash(
            password
        )

    def check_password(self, password):

        return check_password_hash(
            self.password_hash,
            password
        )