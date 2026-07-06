"""add_thinking_column

Revision ID: 53c5adc10cfa
Revises: 2f4a0b1c9d8e
Create Date: 2026-06-26 21:55:46.667490
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '53c5adc10cfa'
down_revision: Union[str, None] = '2f4a0b1c9d8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('chat_messages', sa.Column('thinking', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('chat_messages', 'thinking')
