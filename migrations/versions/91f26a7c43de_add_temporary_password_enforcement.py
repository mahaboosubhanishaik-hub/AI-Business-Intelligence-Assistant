"""add forced password change state

Revision ID: 91f26a7c43de
Revises: 2a95c7d6e401
Create Date: 2026-11-24

"""
from alembic import op
import sqlalchemy as sa


revision = "91f26a7c43de"
down_revision = "2a95c7d6e401"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false()
        )
    )


def downgrade():
    op.drop_column("users", "must_change_password")
