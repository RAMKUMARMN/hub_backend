"""merge notification and chat migration heads

Revision ID: a09b863dc465
Revises: 6531a72e40ab, 3ad97c947a94
Create Date: 2026-07-20 21:01:44.326718
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a09b863dc465'
down_revision: Union[str, None] = ('6531a72e40ab', '3ad97c947a94')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
