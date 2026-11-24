from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("admin.login"))
        if not current_user.is_admin:
            flash("Administrator access is required.", "danger")
            return redirect(url_for("main.dashboard"))
        return view(*args, **kwargs)

    return wrapped_view
