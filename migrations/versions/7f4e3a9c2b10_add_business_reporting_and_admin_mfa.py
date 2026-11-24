"""add admin MFA, login lockout, and monthly budgets

Revision ID: 7f4e3a9c2b10
Revises: 3c14e6a2b971
Create Date: 2026-11-24

"""
from alembic import op
import sqlalchemy as sa


revision = "7f4e3a9c2b10"
down_revision = "3c14e6a2b971"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("admin_mfa_secret_encrypted", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("admin_mfa_recovery_codes", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "admin_mfa_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false()
            )
        )
        batch_op.add_column(
            sa.Column(
                "failed_login_attempts",
                sa.Integer(),
                nullable=False,
                server_default="0"
            )
        )
        batch_op.add_column(sa.Column("login_locked_until", sa.DateTime(), nullable=True))

    op.create_table(
        "monthly_budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("date_column", sa.String(length=255), nullable=False),
        sa.Column("value_column", sa.String(length=255), nullable=False),
        sa.Column("group_column", sa.String(length=255), nullable=False),
        sa.Column("group_value", sa.String(length=255), nullable=False),
        sa.Column("budget_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "dataset_id",
            "period_start",
            "date_column",
            "value_column",
            "group_column",
            "group_value",
            name="uq_monthly_budget_scope"
        )
    )
    op.create_index("ix_monthly_budgets_user_id", "monthly_budgets", ["user_id"])
    op.create_index("ix_monthly_budgets_dataset_id", "monthly_budgets", ["dataset_id"])
    op.create_index("ix_monthly_budgets_period_start", "monthly_budgets", ["period_start"])


def downgrade():
    op.drop_index("ix_monthly_budgets_period_start", table_name="monthly_budgets")
    op.drop_index("ix_monthly_budgets_dataset_id", table_name="monthly_budgets")
    op.drop_index("ix_monthly_budgets_user_id", table_name="monthly_budgets")
    op.drop_table("monthly_budgets")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("login_locked_until")
        batch_op.drop_column("failed_login_attempts")
        batch_op.drop_column("admin_mfa_enabled")
        batch_op.drop_column("admin_mfa_recovery_codes")
        batch_op.drop_column("admin_mfa_secret_encrypted")
