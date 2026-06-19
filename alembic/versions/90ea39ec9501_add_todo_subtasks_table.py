"""add todo subtasks table

Revision ID: 90ea39ec9501
Revises: c0c7b32162c8
Create Date: 2026-06-18 16:37:30.237495
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '90ea39ec9501'
down_revision: Union[str, None] = 'c0c7b32162c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('todo_subtasks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('todo_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('completed', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['todo_id'], ['todos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('todo_subtasks')

