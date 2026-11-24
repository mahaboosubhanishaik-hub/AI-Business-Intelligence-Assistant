import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for
)
from flask_login import current_user, login_user
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError

from app import db, limiter
from app.decorators import admin_required
from app.models.activity_log import ActivityLog
from app.models.dataset import Dataset
from app.models.quality_audit import QualityAudit
from app.models.user import User
from app.services.activity_log import record_activity
from app.services.auth_security import (
    account_login_locked,
    clear_login_failures,
    record_login_failure,
)


admin = Blueprint("admin", __name__, url_prefix="/admin")

ANALYSIS_EVENTS = ("analytics_view", "ai_assistant")
TEMPORARY_PASSWORD_LIFETIME = timedelta(hours=24)


@admin.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(
            User.role == "admin",
            or_(
                func.lower(User.username) == identifier,
                func.lower(User.email) == identifier
            )
        ).first()

        if (
            user
            and user.active
            and not account_login_locked(user)
            and user.check_password(password)
        ):
            clear_login_failures(user)
            record_activity(user.id, "admin_login", "Administrator signed in")
            db.session.commit()
            login_user(user)
            session.permanent = True
            return redirect(url_for("admin.dashboard"))

        record_login_failure(user)

        flash(
            "Sign-in failed or access is temporarily locked. Check the administrator credentials or try again later.",
            "danger"
        )

    return render_template("admin_login.html")


@admin.route("/")
@admin.route("/dashboard")
@admin_required
def dashboard():
    total_users = User.query.count()
    active_users = User.query.filter_by(active=True).count()
    total_datasets = Dataset.query.count()
    analyses_performed = (
        QualityAudit.query.count()
        + ActivityLog.query.filter(
            ActivityLog.event_type.in_(ANALYSIS_EVENTS)
        ).count()
    )
    users = User.query.order_by(User.id.desc()).all()
    recent_activity = (
        ActivityLog.query
        .order_by(ActivityLog.created_at.desc())
        .limit(30)
        .all()
    )

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        active_users=active_users,
        total_datasets=total_datasets,
        analyses_performed=analyses_performed,
        users=users,
        recent_activity=recent_activity
    )


@admin.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.is_admin or user.id == current_user.id:
        abort(403)

    user.active = not user.active
    state = "activated" if user.active else "deactivated"
    record_activity(
        current_user.id,
        "user_status_changed",
        f"Administrator {state} user {user.username}"
    )
    db.session.commit()
    flash(f"Business account {user.username} was {state}.", "success")
    return redirect(url_for("admin.dashboard"))


@admin.route("/issue-temporary-password", methods=["POST"])
@admin_required
def issue_temporary_password():
    email = request.form.get("email", "").strip().lower()
    if (
        len(email) > 120
        or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
    ):
        flash(
            "Enter the business account's registered email address.",
            "danger"
        )
        return redirect(url_for("admin.dashboard"))

    user = User.query.filter(
        func.lower(User.email) == email,
        User.role != "admin"
    ).first()
    if user is None:
        flash(
            "No business account was found for that registered email.",
            "danger"
        )
        return redirect(url_for("admin.dashboard"))
    if not user.active:
        flash(
            "This business account is inactive. Activate it before issuing a temporary password.",
            "danger"
        )
        return redirect(url_for("admin.dashboard"))

    temporary_password = secrets.token_urlsafe(24)
    issued_at = datetime.now(timezone.utc).replace(tzinfo=None)
    user.set_password(temporary_password)
    user.must_change_password = True
    user.temporary_password_expires_at = (
        issued_at + TEMPORARY_PASSWORD_LIFETIME
    )
    user.temporary_password_used_at = None

    try:
        db.session.flush()
        record_activity(
            current_user.id,
            "temporary_password_issued",
            f"Issued a temporary password to business account {user.username}"
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception(
            "Could not save a temporary password for client id %s",
            user.id
        )
        flash(
            "The temporary password update failed. Check the account before "
            "retrying.",
            "danger"
        )
        return redirect(url_for("admin.dashboard"))

    response = make_response(
        render_template(
            "temporary_password_issued.html",
            user=user,
            temporary_password=temporary_password
        )
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response
