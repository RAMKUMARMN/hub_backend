"""add reminder_sent to todos

Revision ID: eda35cc76200
Revises: 0002_poll_responses
Create Date: 2026-06-30 23:42:57.862720
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'eda35cc76200'
down_revision: Union[str, None] = '0002_poll_responses'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'todos',
        sa.Column('reminder_sent', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('todos', 'reminder_sent')