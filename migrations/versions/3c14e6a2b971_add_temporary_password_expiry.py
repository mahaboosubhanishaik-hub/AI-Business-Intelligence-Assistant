"""add temporary password expiry and single-use timestamps

Revision ID: 3c14e6a2b971
Revises: 91f26a7c43de
Create Date: 2026-11-24

"""
from alembic import op
import sqlalchemy as sa


revision = "3c14e6a2b971"
down_revision = "91f26a7c43de"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("temporary_password_expires_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("temporary_password_used_at", sa.DateTime(), nullable=True)
    )


def downgrade():
    op.drop_column("users", "temporary_password_used_at")
    op.drop_column("users", "temporary_password_expires_at")
