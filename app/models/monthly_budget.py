from datetime import datetime

from app import db


class MonthlyBudget(db.Model):
    __tablename__ = "monthly_budgets"
    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "dataset_id",
            "period_start",
            "date_column",
            "value_column",
            "group_column",
            "group_value",
            name="uq_monthly_budget_scope"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    dataset_id = db.Column(
        db.Integer,
        db.ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    period_start = db.Column(db.Date, nullable=False, index=True)
    date_column = db.Column(db.String(255), nullable=False)
    value_column = db.Column(db.String(255), nullable=False)
    group_column = db.Column(db.String(255), nullable=False, default="")
    group_value = db.Column(db.String(255), nullable=False, default="")
    budget_amount = db.Column(db.Numeric(18, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    dataset = db.relationship("Dataset", back_populates="monthly_budgets")
