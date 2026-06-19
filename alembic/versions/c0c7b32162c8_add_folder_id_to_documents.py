"""add folder id to documents

Revision ID: c0c7b32162c8
Revises: ba484b9457ae
Create Date: 2026-06-18 16:37:18.313817
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c0c7b32162c8'
down_revision: Union[str, None] = 'ba484b9457ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('folder_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_documents_folder_id_document_folders', 'documents', 'document_folders', ['folder_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_documents_folder_id_document_folders', 'documents', type_='foreignkey')
    op.drop_column('documents', 'folder_id')

