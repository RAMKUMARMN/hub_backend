"""merge heads

Revision ID: 82431763782b
Revises: a11122233344, 74ef57f50ecc, 90ea39ec9501, 9ea8bc6243f1
Create Date: 2026-06-19 16:08:24.771965
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '82431763782b'
down_revision: Union[str, None] = ('a11122233344', '74ef57f50ecc', '90ea39ec9501', '9ea8bc6243f1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
