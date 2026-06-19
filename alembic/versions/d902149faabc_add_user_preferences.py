"""add_user_preferences

Revision ID: d902149faabc
Revises: 6ea92154e6f7
Create Date: 2026-06-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d902149faabc"
down_revision: Union[str, None] = "6ea92154e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("theme", sa.String(length=20), nullable=False),
        sa.Column("notification_settings", postgresql.JSONB(), nullable=False),
        sa.Column("security_settings", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE"
        ),

        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id")
    )


def downgrade():
    op.drop_table("user_preferences")