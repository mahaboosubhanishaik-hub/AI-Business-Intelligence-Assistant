from datetime import datetime, timedelta, timezone

from app import db


LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCKOUT_DURATION = timedelta(minutes=15)


def account_login_locked(user, now=None):
    if user is None or user.login_locked_until is None:
        return False
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    return user.login_locked_until > now


def record_login_failure(user, now=None):
    if user is None or not user.active:
        return
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    if user.login_locked_until and user.login_locked_until <= now:
        user.failed_login_attempts = 0
        user.login_locked_until = None
    if account_login_locked(user, now):
        return

    user.failed_login_attempts += 1
    if user.failed_login_attempts >= LOGIN_FAILURE_LIMIT:
        user.failed_login_attempts = 0
        user.login_locked_until = now + LOGIN_LOCKOUT_DURATION
    db.session.commit()


def clear_login_failures(user):
    user.failed_login_attempts = 0
    user.login_locked_until = None
