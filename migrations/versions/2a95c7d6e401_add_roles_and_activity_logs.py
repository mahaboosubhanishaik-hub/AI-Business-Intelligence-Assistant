"""add roles, active state, usernames, and activity logs

Revision ID: 2a95c7d6e401
Revises: 4f24b69b3f2d
Create Date: 2026-11-24

"""
from alembic import op
import sqlalchemy as sa


revision = "2a95c7d6e401"
down_revision = "4f24b69b3f2d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("username", sa.String(length=40), nullable=True))
        batch_op.add_column(
            sa.Column(
                "role",
                sa.String(length=20),
                nullable=False,
                server_default="user"
            )
        )
        batch_op.add_column(
            sa.Column(
                "active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true()
            )
        )

    op.execute(
        "UPDATE users "
        "SET username = 'user-' || CAST(id AS VARCHAR) "
        "WHERE username IS NULL"
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "username",
            existing_type=sa.String(length=40),
            nullable=False
        )
        batch_op.create_index("ix_users_username", ["username"], unique=True)

    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_activity_logs_user_id", "activity_logs", ["user_id"])
    op.create_index("ix_activity_logs_dataset_id", "activity_logs", ["dataset_id"])
    op.create_index("ix_activity_logs_event_type", "activity_logs", ["event_type"])
    op.create_index("ix_activity_logs_created_at", "activity_logs", ["created_at"])


def downgrade():
    op.drop_index("ix_activity_logs_created_at", table_name="activity_logs")
    op.drop_index("ix_activity_logs_event_type", table_name="activity_logs")
    op.drop_index("ix_activity_logs_dataset_id", table_name="activity_logs")
    op.drop_index("ix_activity_logs_user_id", table_name="activity_logs")
    op.drop_table("activity_logs")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_username")
        batch_op.drop_column("active")
        batch_op.drop_column("role")
        batch_op.drop_column("username")
