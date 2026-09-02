from datetime import datetime
from app import db


class QualityAudit(db.Model):
    """
    Model for persisting historical DQM data quality snapshots per dataset analysis.
    Used for monitoring quality degradation over time and generating automated alerts.
    """
    __tablename__ = "quality_audits"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    dataset_id = db.Column(
        db.Integer,
        db.ForeignKey("datasets.id"),
        nullable=False,
        index=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    quality_score = db.Column(
        db.Float,
        nullable=False
    )

    status = db.Column(
        db.String(50),
        nullable=False
    )

    missing_count = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    duplicate_count = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    outlier_count = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    suspicious_count = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    audited_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    dataset = db.relationship(
        "Dataset",
        backref=db.backref("quality_audits", lazy=True, cascade="all, delete-orphan")
    )
