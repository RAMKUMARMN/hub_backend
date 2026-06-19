"""add notes table

Revision ID: f5878eee5eeb
Revises: 6ea92154e6f7
Create Date: 2026-06-18 16:36:47.275457
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f5878eee5eeb'
down_revision: Union[str, None] = '6ea92154e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('notes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('tags', sa.ARRAY(sa.String()), server_default='{}', nullable=False),
    sa.Column('is_pinned', sa.Boolean(), nullable=False),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('notes')

