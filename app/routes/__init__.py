import csv
import io
from datetime import datetime, time, timedelta

from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for
)

from flask_login import current_user, login_required
from sqlalchemy import or_

from app.models.activity_log import ActivityLog
from app.models.dataset import Dataset
from app.models.quality_audit import QualityAudit


main = Blueprint(
    "main",
    __name__
)


@main.route("/")
def home():

    return render_template(
        "home.html"
    )


@main.route("/dashboard")
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))

    recent_audits = (
        QualityAudit.query
        .filter_by(user_id=current_user.id)
        .order_by(QualityAudit.audited_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard.html",
        dataset_count=Dataset.query.filter_by(user_id=current_user.id).count(),
        recent_audits=recent_audits
    )


@main.route("/analysis-history")
@login_required
def analysis_history():
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))

    search = request.args.get("q", "").strip()[:100]
    start_text = request.args.get("start_date", "").strip()
    end_text = request.args.get("end_date", "").strip()
    start_date = _parse_history_date(start_text, "start")
    end_date = _parse_history_date(end_text, "end")
    if start_date and end_date and start_date > end_date:
        flash("The start date must be on or before the end date.", "danger")
        start_date = None
        end_date = None

    activity_query = (
        ActivityLog.query
        .filter_by(user_id=current_user.id)
        .filter(ActivityLog.event_type.in_(
            ("analytics_view", "ai_assistant", "business_comparison")
        ))
    )
    audit_query = QualityAudit.query.filter_by(user_id=current_user.id)

    if search:
        pattern = f"%{search}%"
        activity_query = activity_query.filter(
            or_(
                ActivityLog.event_type.ilike(pattern),
                ActivityLog.description.ilike(pattern),
                ActivityLog.dataset.has(Dataset.name.ilike(pattern))
            )
        )
        audit_query = audit_query.filter(
            or_(
                QualityAudit.status.ilike(pattern),
                QualityAudit.dataset.has(Dataset.name.ilike(pattern))
            )
        )

    if start_date:
        start_datetime = datetime.combine(start_date, time.min)
        activity_query = activity_query.filter(
            ActivityLog.created_at >= start_datetime
        )
        audit_query = audit_query.filter(
            QualityAudit.audited_at >= start_datetime
        )
    if end_date:
        exclusive_end = datetime.combine(end_date + timedelta(days=1), time.min)
        activity_query = activity_query.filter(
            ActivityLog.created_at < exclusive_end
        )
        audit_query = audit_query.filter(
            QualityAudit.audited_at < exclusive_end
        )

    if request.args.get("export") == "csv":
        return _export_analysis_history(
            activity_query.order_by(ActivityLog.created_at.desc()).all(),
            audit_query.order_by(QualityAudit.audited_at.desc()).all()
        )

    history = (
        activity_query
        .order_by(ActivityLog.created_at.desc())
        .limit(100)
        .all()
    )
    quality_audits = (
        audit_query
        .order_by(QualityAudit.audited_at.desc())
        .limit(100)
        .all()
    )
    return render_template(
        "analysis_history.html",
        history=history,
        quality_audits=quality_audits,
        search=search,
        start_date=start_text,
        end_date=end_text
    )


def _parse_history_date(value, field_name):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        flash(f"Enter a valid {field_name} date.", "danger")
        return None


def _csv_safe(value):
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def _export_analysis_history(history, quality_audits):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("Record type", "Date", "Activity or score", "Dataset", "Details"))

    records = []
    for entry in history:
        records.append((
            entry.created_at,
            "Activity",
            entry.event_type,
            (
                entry.dataset.name
                if entry.dataset
                else "Dataset removed" if entry.dataset_id else ""
            ),
            entry.description
        ))
    for audit in quality_audits:
        records.append((
            audit.audited_at,
            "Data quality",
            f"{audit.quality_score:.1f}% ({audit.status})",
            audit.dataset.name if audit.dataset else "Dataset removed",
            (
                f"Missing: {audit.missing_count}; duplicates: {audit.duplicate_count}; "
                f"outliers: {audit.outlier_count}; suspicious: {audit.suspicious_count}"
            )
        ))

    for created_at, record_type, label, dataset_name, details in sorted(
        records,
        key=lambda record: record[0],
        reverse=True
    ):
        writer.writerow(
            _csv_safe(value)
            for value in (
                record_type,
                created_at.strftime("%Y-%m-%d %H:%M"),
                label,
                dataset_name,
                details
            )
        )

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = (
        'attachment; filename="analysis-history.csv"'
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response