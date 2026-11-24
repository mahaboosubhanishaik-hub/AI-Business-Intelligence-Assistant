import os

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash
)

from flask_login import (
    login_required,
    current_user
)

from app.models.dataset import Dataset
from app.services.data_loader import load_dataset
from app.services.analytics import generate_analytics
from app.services.data_quality import evaluate_data_quality
from app.services.activity_log import record_activity
from app import db


analytics = Blueprint(
    "analytics",
    __name__,
    url_prefix="/analytics"
)


UPLOAD_FOLDER = os.path.join(
    os.getcwd(),
    "uploads"
)


# ==========================================
# ANALYTICS DASHBOARD
# ==========================================

@analytics.route("/<int:dataset_id>")
@login_required
def dashboard(dataset_id):

    # --------------------------------------
    # SECURITY & OWNERSHIP CHECK
    # --------------------------------------
    dataset = Dataset.query.filter_by(
        id=dataset_id,
        user_id=current_user.id
    ).first_or_404()

    # --------------------------------------
    # FILE PATH CHECK
    # --------------------------------------
    filepath = os.path.join(
        UPLOAD_FOLDER,
        dataset.filename
    )

    if not os.path.exists(filepath):
        flash("This data file is unavailable. Upload it again to continue.", "danger")
        return redirect(url_for("data.datasets"))

    try:
        # ----------------------------------
        # LOAD DATASET
        # ----------------------------------
        df = load_dataset(filepath)

        # ----------------------------------
        # GENERATE BI ANALYTICS & DQM REPORT
        # ----------------------------------
        analytics_data = generate_analytics(df)
        quality_report = evaluate_data_quality(df)
        record_activity(
            current_user.id,
            "analytics_view",
            "Viewed dataset analytics",
            dataset_id=dataset.id
        )
        db.session.commit()

        # ----------------------------------
        # RENDER ANALYTICS DASHBOARD
        # ----------------------------------
        return render_template(
            "analytics.html",
            dataset=dataset,
            analytics=analytics_data,
            quality_report=quality_report
        )

    except Exception:
        flash("We could not analyze this data. Please try again.", "danger")
        return redirect(url_for("data.datasets"))