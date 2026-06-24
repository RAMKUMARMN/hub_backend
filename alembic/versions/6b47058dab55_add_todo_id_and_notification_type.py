"""add todo_id and notification_type

Revision ID: 6b47058dab55
Revises: 8b90a77be6a3
Create Date: 2026-06-20 00:45:44.819713
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6b47058dab55'
down_revision: Union[str, None] = '8b90a77be6a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==============================
    # 1. ADD NEW COLUMNS (SAFE)
    # ==============================

    op.add_column(
        "user_notifications",
        sa.Column("todo_id", sa.UUID(), nullable=True),
    )

    op.add_column(
        "user_notifications",
        sa.Column("notification_type", sa.String(), nullable=True),
    )

    # ==============================
    # 2. BACKFILL OLD DATA
    # ==============================

    op.execute("""
        UPDATE user_notifications
        SET notification_type = 'LEGACY'
        WHERE notification_type IS NULL
    """)

    op.execute("""
        UPDATE user_notifications
        SET title = COALESCE(title, 'Notification')
    """)

    op.execute("""
        UPDATE user_notifications
        SET message = COALESCE(message, '')
    """)

    # ==============================
    # 3. ENFORCE NOT NULL SAFELY
    # ==============================

    op.alter_column(
        "user_notifications",
        "notification_type",
        nullable=False,
    )

    op.alter_column(
        "user_notifications",
        "title",
        nullable=False,
    )

    op.alter_column(
        "user_notifications",
        "message",
        nullable=False,
    )

    # ==============================
    # 4. INDEXES (FOR PERFORMANCE)
    # ==============================

    op.create_index(
        op.f("ix_user_notifications_notification_type"),
        "user_notifications",
        ["notification_type"],
        unique=False,
    )

    op.create_index(
        op.f("ix_user_notifications_todo_id"),
        "user_notifications",
        ["todo_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_user_notifications_user_id"),
        "user_notifications",
        ["user_id"],
        unique=False,
    )

    # ==============================
    # 5. FOREIGN KEY RELATION
    # ==============================

    op.create_foreign_key(
        None,
        "user_notifications",
        "todos",
        ["todo_id"],
        ["id"],
    )

    # ==============================
    # 6. REMOVE OLD COLUMN
    # ==============================

    op.drop_column("user_notifications", "type")


def downgrade() -> None:
    # ==============================
    # REVERT MIGRATION
    # ==============================

    op.add_column(
        "user_notifications",
        sa.Column("type", sa.VARCHAR(), nullable=True),
    )

    op.drop_constraint(
        None,
        "user_notifications",
        type_="foreignkey"
    )

    op.drop_index(
        op.f("ix_user_notifications_user_id"),
        table_name="user_notifications"
    )

    op.drop_index(
        op.f("ix_user_notifications_todo_id"),
        table_name="user_notifications"
    )

    op.drop_index(
        op.f("ix_user_notifications_notification_type"),
        table_name="user_notifications"
    )

    op.alter_column(
        "user_notifications",
        "message",
        existing_type=sa.VARCHAR(),
        nullable=True,
    )

    op.alter_column(
        "user_notifications",
        "title",
        existing_type=sa.VARCHAR(),
        nullable=True,
    )

    op.alter_column(
        "user_notifications",
        "user_id",
        existing_type=sa.UUID(),
        nullable=True,
    )

    op.drop_column("user_notifications", "notification_type")
    op.drop_column("user_notifications", "todo_id")