from datetime import datetime, timezone

from app import db


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    dataset_id = db.Column(
        db.Integer,
        db.ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    event_type = db.Column(db.String(40), nullable=False, index=True)
    description = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        index=True
    )

    actor = db.relationship(
        "User",
        backref=db.backref("activity_logs", lazy=True, passive_deletes=True)
    )
    dataset = db.relationship("Dataset")
