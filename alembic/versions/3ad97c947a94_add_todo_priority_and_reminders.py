"""add todo priority and reminders

Revision ID: 3ad97c947a94
Revises: 3be13befa107
"""

from typing import Sequence, Union

from alembic import op

revision = "3ad97c947a94"
down_revision = "3be13befa107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # priority and reminder_time were already added in
    # 6ea92154e6f7_add_priority_and_reminder_to_todos.
    #
    # This migration became redundant after the migration
    # history was merged.
    pass


def downgrade() -> None:
    pass