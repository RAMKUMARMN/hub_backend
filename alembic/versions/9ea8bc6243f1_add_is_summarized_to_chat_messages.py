"""add is_summarized to chat_messages

Revision ID: 9ea8bc6243f1
Revises: 6ea92154e6f7
Create Date: 2026-06-19 10:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9ea8bc6243f1'
down_revision: Union[str, None] = '6ea92154e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'chat_messages',
        sa.Column(
            'is_summarized',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            default=False
        )
    )


def downgrade() -> None:
    op.drop_column('chat_messages', 'is_summarized')
