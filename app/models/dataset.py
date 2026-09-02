from datetime import datetime
from app import db


class Dataset(db.Model):

    __tablename__ = "datasets"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    name = db.Column(
        db.String(255),
        nullable=False
    )

    filename = db.Column(
        db.String(255),
        nullable=False
    )

    source_type = db.Column(
        db.String(20),
        nullable=False
    )

    rows = db.Column(
        db.Integer,
        nullable=True
    )

    columns = db.Column(
        db.Integer,
        nullable=True
    )

    file_size_bytes = db.Column(
        db.BigInteger,
        nullable=True
    )

    uploaded_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    @property
    def file_size_human(self):
        """Format file_size_bytes into human readable string (KB, MB)."""
        if not self.file_size_bytes:
            return "Unknown"
        size = float(self.file_size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"