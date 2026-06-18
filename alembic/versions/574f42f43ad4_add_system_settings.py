"""add_system_settings

Revision ID: e123456789ab
Revises: d902149faabc
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e123456789ab"
down_revision: Union[str, None] = "d902149faabc"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "system_settings",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "key",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "value",
            postgresql.JSONB(),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "key",
            name="uq_system_settings_key"
        ),
    )


def downgrade():
    op.drop_table("system_settings")