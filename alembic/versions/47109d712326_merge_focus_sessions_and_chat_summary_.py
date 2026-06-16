"""merge focus sessions and chat summary heads

Revision ID: 47109d712326
Revises: 0003_add_chat_session_summary, 16c6253c5182
Create Date: 2026-06-16 12:33:26.447366
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '47109d712326'
down_revision: Union[str, None] = ('0003_add_chat_session_summary', '16c6253c5182')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
