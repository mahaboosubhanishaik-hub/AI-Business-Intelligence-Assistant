import os
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify
)
from flask_login import (
    login_required,
    current_user
)

from app.models.dataset import Dataset
from app.services.data_loader import load_dataset
from app.services.data_quality import evaluate_data_quality
from app.services.analytics import generate_analytics
from app.services.ai_service import (
    generate_ai_summary,
    ask_ai_assistant
)


ai = Blueprint(
    "ai",
    __name__,
    url_prefix="/ai"
)


UPLOAD_FOLDER = os.path.join(
    os.getcwd(),
    "uploads"
)


@ai.route("/assistant/<int:dataset_id>", methods=["GET", "POST"])
@login_required
def assistant(dataset_id):
    # Security & Ownership Check
    dataset = Dataset.query.filter_by(
        id=dataset_id,
        user_id=current_user.id
    ).first_or_404()

    filepath = os.path.join(UPLOAD_FOLDER, dataset.filename)

    if not os.path.exists(filepath):
        if request.method == "POST":
            return jsonify({"answer": "Dataset file not found.", "status": "error"}), 404
        flash("Dataset file could not be found on server.", "danger")
        return redirect(url_for("data.datasets"))

    try:
        df = load_dataset(filepath)
        quality_report = evaluate_data_quality(df)
        analytics_data = generate_analytics(df)

        if request.method == "POST":
            data = request.get_json(silent=True) or request.form
            question = data.get("question", "").strip()
            res = ask_ai_assistant(df, dataset.name, quality_report, analytics_data, question)
            return jsonify(res)

        # GET request
        ai_summary = generate_ai_summary(df, dataset.name, quality_report, analytics_data)

        return render_template(
            "ai_assistant.html",
            dataset=dataset,
            quality_report=quality_report,
            analytics=analytics_data,
            ai_summary=ai_summary
        )

    except Exception:
        if request.method == "POST":
            return jsonify({"answer": "Error processing request.", "status": "error"}), 500
        flash("Unable to load AI Assistant for this dataset.", "danger")
        return redirect(url_for("data.datasets"))
