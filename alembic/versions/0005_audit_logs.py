"""Add audit_logs table

Revision ID: 0005_audit_logs
Revises: 0004_user_preferences
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_audit_logs"
down_revision: Union[str, None] = "0004_user_preferences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on = None

def upgrade():
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "resource_type",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "resource_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "details",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
    )
def downgrade():
    op.drop_table("audit_logs")