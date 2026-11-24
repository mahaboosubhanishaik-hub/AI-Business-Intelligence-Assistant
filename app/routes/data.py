import os
import uuid

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
)
from flask_login import (
    login_required,
    current_user
)
from werkzeug.utils import secure_filename

from app import db
from app import limiter
from app.models.dataset import Dataset
from app.services.data_loader import (
    allowed_file,
    load_dataset
)
from app.services.data_profiler import (
    profile_dataset
)
from app.services.data_quality import (
    evaluate_data_quality
)
from app.services.monitoring import (
    audit_and_monitor_quality
)
from app.services.activity_log import record_activity


data = Blueprint(
    "data",
    __name__,
    url_prefix="/data"
)


UPLOAD_FOLDER = os.path.join(
    os.getcwd(),
    "uploads"
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


@data.route("/datasets")
@login_required
def datasets():
    user_datasets = (
        Dataset.query
        .filter_by(user_id=current_user.id)
        .order_by(Dataset.uploaded_at.desc())
        .all()
    )

    return render_template(
        "datasets.html",
        datasets=user_datasets
    )


@data.route("/upload", methods=["GET", "POST"])
@login_required
@limiter.limit("100 per hour", methods=["POST"])
def upload():
    if request.method == "GET":
        return render_template("upload.html")

    file = request.files.get("file")

    if not file or file.filename == "":
        flash("Select a file to continue.", "danger")
        return redirect(url_for("data.upload"))

    if not allowed_file(file.filename):
        flash("Choose a CSV or Excel file (.xlsx or .xls).", "danger")
        return redirect(url_for("data.upload"))

    original_filename = secure_filename(file.filename)
    extension = os.path.splitext(original_filename)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}{extension}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)

    try:
        # Save file to upload directory
        file.save(filepath)
        file_size_bytes = os.path.getsize(filepath)

        # Load dataset & validate content
        df = load_dataset(filepath)

        # Profile dataset
        profile = profile_dataset(df)

        # Save record to database
        dataset = Dataset(
            user_id=current_user.id,
            name=os.path.splitext(original_filename)[0],
            filename=unique_filename,
            source_type=extension.replace(".", ""),
            rows=profile["rows"],
            columns=profile["columns"],
            file_size_bytes=file_size_bytes
        )

        db.session.add(dataset)
        db.session.flush()
        record_activity(
            current_user.id,
            "dataset_uploaded",
            "Uploaded a dataset",
            dataset_id=dataset.id
        )
        db.session.commit()

        flash("Business data uploaded successfully. Your file is ready to review.", "success")

        # Preview first 20 rows
        preview = (
            df.head(20)
            .fillna("")
            .to_dict(orient="records")
        )

        return render_template(
            "data_profile.html",
            dataset=dataset,
            profile=profile,
            preview=preview
        )

    except ValueError as val_err:
        db.session.rollback()
        if os.path.exists(filepath):
            os.remove(filepath)
        flash(str(val_err), "danger")
        return redirect(url_for("data.upload"))

    except Exception:
        db.session.rollback()
        if os.path.exists(filepath):
            os.remove(filepath)
        flash("We could not process this file. Check that it is a valid CSV or Excel file and try again.", "danger")
        return redirect(url_for("data.upload"))


@data.route("/view/<int:dataset_id>")
@login_required
def view_dataset(dataset_id):
    # Ownership Security Check
    dataset = Dataset.query.filter_by(
        id=dataset_id,
        user_id=current_user.id
    ).first_or_404()

    filepath = os.path.join(UPLOAD_FOLDER, dataset.filename)

    if not os.path.exists(filepath):
        flash("This data file is unavailable. Upload it again to continue.", "danger")
        return redirect(url_for("data.datasets"))

    try:
        df = load_dataset(filepath)
        profile = profile_dataset(df)
        preview = (
            df.head(20)
            .fillna("")
            .to_dict(orient="records")
        )

        return render_template(
            "data_profile.html",
            dataset=dataset,
            profile=profile,
            preview=preview
        )

    except Exception:
        flash("We could not read this file. Check that it is a valid CSV or Excel file.", "danger")
        return redirect(url_for("data.datasets"))


@data.route("/preview/<int:dataset_id>")
@login_required
def preview_dataset(dataset_id):
    # Ownership Security Check
    dataset = Dataset.query.filter_by(
        id=dataset_id,
        user_id=current_user.id
    ).first_or_404()

    filepath = os.path.join(UPLOAD_FOLDER, dataset.filename)

    if not os.path.exists(filepath):
        flash("This data file is unavailable. Upload it again to continue.", "danger")
        return redirect(url_for("data.datasets"))

    try:
        df = load_dataset(filepath, nrows=50)
        preview = (
            df.head(50)
            .fillna("")
            .to_dict(orient="records")
        )
        columns = list(df.columns)

        return render_template(
            "data_preview.html",
            dataset=dataset,
            columns=columns,
            preview=preview
        )

    except Exception:
        flash("We could not create a preview. Please try again.", "danger")
        return redirect(url_for("data.datasets"))


@data.route("/quality/<int:dataset_id>")
@login_required
def quality_analysis(dataset_id):
    # Ownership Security Check
    dataset = Dataset.query.filter_by(
        id=dataset_id,
        user_id=current_user.id
    ).first_or_404()

    filepath = os.path.join(UPLOAD_FOLDER, dataset.filename)

    if not os.path.exists(filepath):
        flash("This data file is unavailable. Upload it again to continue.", "danger")
        return redirect(url_for("data.datasets"))

    try:
        df = load_dataset(filepath)
        report = evaluate_data_quality(df)

        # Audit and monitor quality history & degradation
        monitoring_data = audit_and_monitor_quality(dataset.id, current_user.id, report)
        record_activity(
            current_user.id,
            "quality_analysis",
            "Ran a data quality analysis",
            dataset_id=dataset.id
        )
        db.session.commit()

        return render_template(
            "data_quality.html",
            dataset=dataset,
            report=report,
            monitoring=monitoring_data
        )

    except Exception:
        flash("We could not complete the data quality check. Please try again.", "danger")
        return redirect(url_for("data.datasets"))


@data.route("/delete/<int:dataset_id>", methods=["POST"])
@login_required
def delete_dataset(dataset_id):
    # Ownership Security Check
    dataset = Dataset.query.filter_by(
        id=dataset_id,
        user_id=current_user.id
    ).first_or_404()

    filepath = os.path.join(UPLOAD_FOLDER, dataset.filename)

    try:
        if os.path.exists(filepath):
            os.remove(filepath)

        record_activity(
            current_user.id,
            "dataset_deleted",
            "Deleted a dataset",
            dataset_id=dataset.id
        )
        db.session.delete(dataset)
        db.session.commit()

        flash(f"Dataset '{dataset.name}' was deleted.", "success")

    except Exception:
        db.session.rollback()
        flash("We could not delete this dataset. Please try again.", "danger")

    return redirect(url_for("data.datasets"))
