"""add document folders table

Revision ID: ba484b9457ae
Revises: f5878eee5eeb
Create Date: 2026-06-18 16:37:05.290356
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ba484b9457ae'
down_revision: Union[str, None] = 'f5878eee5eeb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('document_folders',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('document_folders')

