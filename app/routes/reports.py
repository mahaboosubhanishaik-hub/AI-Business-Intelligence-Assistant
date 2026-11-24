import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for
)
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.activity_log import ActivityLog
from app.models.dataset import Dataset
from app.models.monthly_budget import MonthlyBudget
from app.models.quality_audit import QualityAudit
from app.services.activity_log import record_activity
from app.services.business_metrics import (
    aggregate_month,
    categorical_values,
    compare_values,
    load_business_dataset,
    numeric_columns
)


reports = Blueprint("reports", __name__, url_prefix="/reports")


@reports.route("/budgets", methods=["GET", "POST"])
@login_required
def budgets():
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        return _save_budget()

    datasets = (
        Dataset.query
        .filter_by(user_id=current_user.id)
        .order_by(Dataset.name.asc())
        .all()
    )
    selected_dataset = _selected_dataset(request.args.get("dataset_id"), datasets)
    try:
        selected_month = _parse_month(request.args.get("month", ""))
    except ValueError:
        flash("Choose a valid month.", "danger")
        selected_month = date.today().replace(day=1)
    group_column = request.args.get("group_column", "").strip()
    frame = None
    columns = []
    values = []
    if selected_dataset:
        try:
            frame = load_business_dataset(selected_dataset)
            columns = [str(column) for column in frame.columns]
            if group_column and group_column in columns:
                values = categorical_values(frame, group_column)
            else:
                group_column = ""
        except (OSError, ValueError):
            current_app.logger.exception(
                "Could not load dataset %s for budget entry",
                selected_dataset.id
            )
            flash("The selected dataset could not be read. Upload it again to continue.", "danger")
            selected_dataset = None

    budget_rows = []
    for budget in (
        MonthlyBudget.query
        .filter_by(user_id=current_user.id, period_start=selected_month)
        .order_by(MonthlyBudget.dataset_id, MonthlyBudget.value_column)
        .all()
    ):
        try:
            budget_frame = load_business_dataset(budget.dataset)
            actual, records = aggregate_month(
                budget_frame,
                budget.period_start,
                budget.date_column,
                budget.value_column,
                budget.group_column,
                budget.group_value
            )
        except (OSError, ValueError):
            current_app.logger.exception(
                "Could not calculate actuals for monthly budget %s",
                budget.id
            )
            actual, records = None, 0
        budget_rows.append({
            "budget": budget,
            "actual": actual,
            "records": records,
            "variance": actual - float(budget.budget_amount) if actual is not None else None
        })

    return _private_render(
        "budgets.html",
        datasets=datasets,
        selected_dataset=selected_dataset,
        selected_month=selected_month.strftime("%Y-%m"),
        columns=columns,
        numeric_columns=numeric_columns(frame) if frame is not None else [],
        group_column=group_column,
        group_values=values,
        budget_rows=budget_rows
    )


def _save_budget():
    dataset_id = _parse_int(request.form.get("dataset_id"))
    dataset = Dataset.query.filter_by(
        id=dataset_id,
        user_id=current_user.id
    ).first_or_404()
    try:
        period_start = _parse_month(request.form.get("month", ""))
    except ValueError:
        flash("Choose a valid month.", "danger")
        return redirect(_budget_url(dataset.id, date.today().replace(day=1)))
    date_column = request.form.get("date_column", "").strip()
    value_column = request.form.get("value_column", "").strip()
    group_column = request.form.get("group_column", "").strip()
    group_value = request.form.get("group_value", "").strip()

    try:
        budget_amount = Decimal(request.form.get("budget_amount", "").strip())
    except (InvalidOperation, AttributeError):
        flash("Enter a valid budget amount.", "danger")
        return redirect(_budget_url(dataset.id, period_start, group_column))

    if (
        not budget_amount.is_finite()
        or budget_amount < 0
        or budget_amount > Decimal("9999999999999999.99")
    ):
        flash("Budget amounts must be between 0 and 9999999999999999.99.", "danger")
        return redirect(_budget_url(dataset.id, period_start, group_column))

    try:
        frame = load_business_dataset(dataset)
        if value_column not in numeric_columns(frame):
            raise ValueError("Choose a column that contains numeric actual values.")
        if group_column:
            if group_column not in frame.columns or not group_value:
                raise ValueError("Choose a valid group column and group value.")
            if len(group_value) > 255 or not (
                frame[group_column].dropna().astype(str).str.strip() == group_value
            ).any():
                raise ValueError("The group value was not found in the selected dataset.")
        elif group_value:
            raise ValueError("Select a group column before entering a group value.")
        aggregate_month(
            frame,
            period_start,
            date_column,
            value_column,
            group_column,
            group_value
        )
    except (OSError, ValueError) as error:
        flash(str(error) if isinstance(error, ValueError) else "The selected dataset could not be read.", "danger")
        return redirect(_budget_url(dataset.id, period_start, group_column))

    budget = MonthlyBudget.query.filter_by(
        user_id=current_user.id,
        dataset_id=dataset.id,
        period_start=period_start,
        date_column=date_column,
        value_column=value_column,
        group_column=group_column,
        group_value=group_value
    ).first()
    if budget is None:
        budget = MonthlyBudget(
            user_id=current_user.id,
            dataset_id=dataset.id,
            period_start=period_start,
            date_column=date_column,
            value_column=value_column,
            group_column=group_column,
            group_value=group_value
        )
        db.session.add(budget)
    budget.budget_amount = budget_amount.quantize(Decimal("0.01"))

    try:
        record_activity(
            current_user.id,
            "budget_updated",
            f"Created or updated a budget for {period_start:%Y-%m}",
            dataset_id=dataset.id
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception(
            "Could not save budget for user id %s",
            current_user.id
        )
        flash("The budget could not be saved. Please try again.", "danger")
        return redirect(_budget_url(dataset.id, period_start, group_column))

    flash("Monthly budget saved.", "success")
    return redirect(_budget_url(dataset.id, period_start, group_column))


@reports.route("/compare")
@login_required
def compare():
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))

    datasets = (
        Dataset.query
        .filter_by(user_id=current_user.id)
        .order_by(Dataset.name.asc())
        .all()
    )
    selected_dataset = _selected_dataset(request.args.get("dataset_id"), datasets)
    columns = []
    numbers = []
    rows = []
    dimensions = []
    if selected_dataset:
        try:
            frame = load_business_dataset(selected_dataset)
            columns = [str(column) for column in frame.columns]
            numbers = numeric_columns(frame)
            value_column = request.args.get("value_column", "").strip()
            group_column = request.args.get("group_column", "").strip()
            date_column = request.args.get("date_column", "").strip()
            if value_column:
                rows, dimensions = compare_values(
                    frame,
                    value_column,
                    group_column,
                    date_column
                )
                record_activity(
                    current_user.id,
                    "business_comparison",
                    f"Compared {value_column} using the selected dataset",
                    dataset_id=selected_dataset.id
                )
                db.session.commit()
        except (OSError, ValueError) as error:
            flash(str(error) if isinstance(error, ValueError) else "The selected dataset could not be read.", "danger")
            selected_dataset = None

    return _private_render(
        "comparison.html",
        datasets=datasets,
        selected_dataset=selected_dataset,
        columns=columns,
        numeric_columns=numbers,
        value_column=request.args.get("value_column", ""),
        group_column=request.args.get("group_column", ""),
        date_column=request.args.get("date_column", ""),
        rows=rows,
        dimensions=dimensions
    )


@reports.route("/monthly")
@login_required
def monthly_report():
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))

    month_value = request.args.get("month", "")
    try:
        period_start = _parse_month(month_value)
    except ValueError:
        flash("Choose a valid report month.", "danger")
        period_start = date.today().replace(day=1)
    period_end = (
        datetime.combine(period_start, time.min)
        + timedelta(days=32)
    ).replace(day=1)
    budget_rows = []
    budgets_for_month = (
        MonthlyBudget.query
        .filter_by(user_id=current_user.id, period_start=period_start)
        .order_by(MonthlyBudget.dataset_id, MonthlyBudget.value_column)
        .all()
    )
    frames = {}
    for budget in budgets_for_month:
        try:
            if budget.dataset_id not in frames:
                frames[budget.dataset_id] = load_business_dataset(budget.dataset)
            actual, records = aggregate_month(
                frames[budget.dataset_id],
                budget.period_start,
                budget.date_column,
                budget.value_column,
                budget.group_column,
                budget.group_value
            )
        except (OSError, ValueError):
            current_app.logger.exception(
                "Could not include budget %s in monthly report",
                budget.id
            )
            actual, records = None, 0
        budget_rows.append({
            "budget": budget,
            "actual": actual,
            "records": records,
            "variance": actual - float(budget.budget_amount) if actual is not None else None
        })

    analysis_count = ActivityLog.query.filter(
        ActivityLog.user_id == current_user.id,
        ActivityLog.event_type.in_(
            ("analytics_view", "ai_assistant", "business_comparison")
        ),
        ActivityLog.created_at >= datetime.combine(period_start, time.min),
        ActivityLog.created_at < period_end
    ).count()
    dataset_count = Dataset.query.filter(
        Dataset.user_id == current_user.id,
        Dataset.uploaded_at >= datetime.combine(period_start, time.min),
        Dataset.uploaded_at < period_end
    ).count()
    average_quality = db.session.query(
        func.avg(QualityAudit.quality_score)
    ).filter(
        QualityAudit.user_id == current_user.id,
        QualityAudit.audited_at >= datetime.combine(period_start, time.min),
        QualityAudit.audited_at < period_end
    ).scalar()

    return _private_render(
        "monthly_report.html",
        report_month=period_start.strftime("%Y-%m"),
        report_title=period_start.strftime("%B %Y"),
        generated_at=datetime.now(timezone.utc),
        budget_rows=budget_rows,
        analysis_count=analysis_count,
        dataset_count=dataset_count,
        average_quality=float(average_quality) if average_quality is not None else None
    )


def _selected_dataset(dataset_id, datasets):
    if not dataset_id:
        return None
    parsed_id = _parse_int(dataset_id)
    selected = next(
        (dataset for dataset in datasets if dataset.id == parsed_id),
        None
    )
    if selected is None:
        flash("Choose a dataset available to your account.", "danger")
    return selected


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_month(value):
    if not value:
        return date.today().replace(day=1)
    if not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError("Invalid month.")
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError:
        raise ValueError("Invalid month.") from None


def _budget_url(dataset_id, period_start, group_column=""):
    return url_for(
        "reports.budgets",
        dataset_id=dataset_id,
        month=period_start.strftime("%Y-%m"),
        group_column=group_column
    )


def _private_render(template, **context):
    response = make_response(render_template(template, **context))
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    return response