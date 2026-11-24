from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    session
)
from datetime import datetime, timezone
from app import limiter
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
import re

from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)

from app import db
from app.models.user import User
from app.services.activity_log import record_activity
from app.services.auth_security import (
    account_login_locked,
    clear_login_failures,
    record_login_failure
)


auth = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth"
)


def dashboard_for_user(user):
    if user.is_admin:
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("main.dashboard"))


@auth.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def register():

    if current_user.is_authenticated:
        return dashboard_for_user(current_user)

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not username or not email or not password:
            flash(
                "All fields are required.",
                "danger"
            )
            return redirect(
                url_for("auth.register")
            )

        if len(name) > 100:
            flash("Name must be 100 characters or fewer.", "danger")
            return redirect(url_for("auth.register"))

        if username == current_app.config["ADMIN_USERNAME"]:
            flash("That business handle is reserved.", "danger")
            return redirect(url_for("auth.register"))

        if not re.fullmatch(r"[a-z0-9_.-]{3,40}", username):
            flash(
                "Business handle must be 3-40 characters and use only letters, numbers, dots, underscores, or hyphens.",
                "danger"
            )
            return redirect(url_for("auth.register"))

        if (
            len(email) > 120
            or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
        ):
            flash("Enter a valid email address.", "danger")
            return redirect(url_for("auth.register"))

        if len(password) < 8 or len(password) > 128:
            flash("Password must be between 8 and 128 characters.", "danger")
            return redirect(url_for("auth.register"))

        existing_user = User.query.filter(
            or_(
                func.lower(User.email) == email,
                func.lower(User.username) == username
            )
        ).first()

        if existing_user:
            flash(
                "That email address or business handle is already in use.",
                "warning"
            )
            return redirect(
                url_for("auth.register")
            )

        user = User(
            name=name,
            username=username,
            email=email
        )

        user.set_password(password)

        db.session.add(user)
        db.session.flush()
        record_activity(user.id, "user_registered", "Created an account")

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That email address or business handle is already in use.", "warning")
            return redirect(url_for("auth.register"))

        flash(
            "Registration successful. Please login.",
            "success"
        )

        return redirect(
            url_for("auth.login")
        )

    return render_template("register.html")


@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return dashboard_for_user(current_user)

    if request.method == "POST":
        identifier = request.form.get(
            "identifier",
            request.form.get("email", "")
        ).strip().lower()
        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter(
            or_(
                func.lower(User.email) == identifier,
                func.lower(User.username) == identifier
            )
        ).first()

        if (
            user
            and user.active
            and not account_login_locked(user)
            and user.check_password(password)
        ):
            if user.is_admin:
                clear_login_failures(user)
                record_activity(user.id, "admin_login", "Administrator signed in")
                db.session.commit()
                login_user(user)
                session.permanent = True
                return dashboard_for_user(user)

            if user.must_change_password:
                user = (
                    User.query
                    .populate_existing()
                    .with_for_update()
                    .filter_by(id=user.id)
                    .first()
                )
                if (
                    user is None
                    or not user.active
                    or not user.check_password(password)
                ):
                    db.session.rollback()
                    flash(
                        "Sign-in failed. Check your business handle or email and password, or contact the administrator if your account is inactive.",
                        "danger"
                    )
                    return render_template("login.html")

                now = datetime.now(timezone.utc).replace(tzinfo=None)
                expires_at = user.temporary_password_expires_at
                if (
                    not user.must_change_password
                    or expires_at is None
                    or expires_at <= now
                ):
                    db.session.rollback()
                    flash(
                        "This temporary password has expired. Ask the administrator to issue a new one.",
                        "danger"
                    )
                    return render_template("login.html")

                if user.temporary_password_used_at is not None:
                    db.session.rollback()
                    flash(
                        "This temporary password has already been used. Ask the administrator to issue a new one.",
                        "danger"
                    )
                    return render_template("login.html")

                user.temporary_password_used_at = now
                clear_login_failures(user)
                record_activity(
                    user.id,
                    "temporary_password_login",
                    "Signed in using an administrator-issued temporary password"
                )
                db.session.commit()
                login_user(user)
                session.permanent = True
                flash(
                    "Set a new password now. This temporary password can only be used once.",
                    "warning"
                )
                return redirect(url_for("auth.change_password"))

            clear_login_failures(user)
            record_activity(user.id, "user_login", "Signed in")
            db.session.commit()
            login_user(user)
            session.permanent = True
            return dashboard_for_user(user)

        record_login_failure(user)
        flash(
            "Sign-in failed or access is temporarily locked. Check your business handle or email and password, or try again later.",
            "danger"
        )

    return render_template("login.html")


@auth.route("/logout", methods=["POST"])
@login_required
def logout():
    record_activity(current_user.id, "user_logout", "Signed out")
    db.session.commit()
    logout_user()
    session.clear()
    flash(
        "You have been logged out.",
        "info"
    )

    return redirect(
        url_for("main.home")
    )


@auth.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = current_user.username
        email = current_user.email

        if not name or len(name) > 100:
            flash("Name is required and must be 100 characters or fewer.", "danger")
            return redirect(url_for("auth.profile"))

        submitted_username = request.form.get("username")
        if submitted_username is not None:
            username = submitted_username.strip().lower()
            if (
                username != current_user.username
                and not re.fullmatch(r"[a-z0-9_.-]{3,40}", username)
            ):
                flash(
                    "Business Handle must be 3-40 characters and use only letters, numbers, dots, underscores, or hyphens.",
                    "danger"
                )
                return redirect(url_for("auth.profile"))

            if (
                not current_user.is_admin
                and username == current_app.config["ADMIN_USERNAME"].strip().lower()
            ):
                flash("That Business Handle is reserved.", "danger")
                return redirect(url_for("auth.profile"))

            existing_user = User.query.filter(
                func.lower(User.username) == username,
                User.id != current_user.id
            ).first()
            if existing_user:
                flash("That Business Handle is already in use.", "warning")
                return redirect(url_for("auth.profile"))

        submitted_email = request.form.get("email")
        if current_user.is_admin and submitted_email is not None:
            email = submitted_email.strip().lower()
            if email != current_user.email:
                if (
                    len(email) > 120
                    or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
                ):
                    flash("Enter a valid email address.", "danger")
                    return redirect(url_for("auth.profile"))

                existing_user = User.query.filter(
                    func.lower(User.email) == email,
                    User.id != current_user.id
                ).first()
                if existing_user:
                    flash("That email address is already in use.", "warning")
                    return redirect(url_for("auth.profile"))

        current_user.name = name
        current_user.username = username
        current_user.email = email
        record_activity(current_user.id, "profile_updated", "Updated profile")
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(
                "That Business Handle or email address is already in use.",
                "warning"
            )
            return redirect(url_for("auth.profile"))

        flash("Your profile was updated.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("profile.html")


@auth.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if (
        current_user.must_change_password
        and current_user.temporary_password_used_at is None
    ):
        logout_user()
        flash(
            "Sign in with the temporary password before changing it.",
            "danger"
        )
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        requires_password_change = current_user.must_change_password

        if not new_password or not confirm_password:
            flash("New password and confirmation are required.", "danger")
            return redirect(url_for("auth.change_password"))

        if not requires_password_change and not current_password:
            flash("Current password is required.", "danger")
            return redirect(url_for("auth.change_password"))

        if (
            not requires_password_change
            and not current_user.check_password(current_password)
        ):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("auth.change_password"))

        if new_password != confirm_password:
            flash("New password and confirmation do not match.", "danger")
            return redirect(url_for("auth.change_password"))

        if len(new_password) < 12 or len(new_password) > 128:
            flash("New password must be between 12 and 128 characters.", "danger")
            return redirect(url_for("auth.change_password"))

        if (
            requires_password_change
            and current_user.check_password(new_password)
        ):
            flash(
                "Choose a password different from your temporary password.",
                "danger"
            )
            return redirect(url_for("auth.change_password"))

        if not requires_password_change and new_password == current_password:
            flash("Choose a password different from your current password.", "danger")
            return redirect(url_for("auth.change_password"))

        current_user.set_password(new_password)
        current_user.must_change_password = False
        current_user.temporary_password_expires_at = None
        current_user.temporary_password_used_at = None
        record_activity(current_user.id, "password_changed", "Changed password")
        db.session.commit()
        flash("Your password has been updated successfully.", "success")
        if requires_password_change:
            return dashboard_for_user(current_user)
        return redirect(url_for("auth.change_password"))

    return render_template("change_password.html")
