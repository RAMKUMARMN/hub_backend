"""add_deleted_at_and_doc_version

Revision ID: 74ef57f50ecc
Revises: 6ea92154e6f7
Create Date: 2026-06-18 16:16:57.015203
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '74ef57f50ecc'
down_revision: Union[str, None] = '6ea92154e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'documents',
        sa.Column(
            'version',
            sa.Integer(),
            nullable=False,
            server_default='1'
        )
    )

    op.drop_column('documents', 'chroma_collection')

    op.add_column(
        'users',
        sa.Column(
            'deleted_at',
            sa.DateTime(timezone=True),
            nullable=True
        )
    )


def downgrade() -> None:
    op.drop_column('users', 'deleted_at')

    op.add_column(
        'documents',
        sa.Column(
            'chroma_collection',
            sa.TEXT(),
            nullable=True
        )
    )

    op.drop_column('documents', 'version')