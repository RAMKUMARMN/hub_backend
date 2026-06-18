"""Add user preference fields to users table

Revision ID: 0004_user_preferences
Revises: 0003_notification_jobs
Create Date: 2026-06-18 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_user_preferences"
down_revision: Union[str, None] = "0003_notification_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on = None
def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "theme",
            sa.String(length=20),
            nullable=False,
            server_default="light",
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "language",
            sa.String(length=20),
            nullable=False,
            server_default="en",
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "timezone",
            sa.String(length=50),
            nullable=False,
            server_default="UTC",
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "email_notifications",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "push_notifications",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade():
    op.drop_column("users", "push_notifications")
    op.drop_column("users", "email_notifications")
    op.drop_column("users", "timezone")
    op.drop_column("users", "language")
    op.drop_column("users", "theme")