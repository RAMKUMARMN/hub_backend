"""add_roles

Revision ID: a11122233344
Revises: f987654321cd
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a11122233344"
down_revision: Union[str, None] = "f987654321cd"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "roles",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "name",
            sa.String(length=50),
            nullable=False,
        ),

        sa.Column(
            "permissions",
            postgresql.JSONB(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "name",
            name="uq_roles_name"
        ),
    )


def downgrade():
    op.drop_table("roles")