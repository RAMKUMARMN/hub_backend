"""remove poll responses

Revision ID: 2f4a0b1c9d8e
Revises: 82431763782b
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "2f4a0b1c9d8e"
down_revision: Union[str, None] = "82431763782b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("poll_responses")


def downgrade() -> None:
    op.create_table(
        "poll_responses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("q1_modules_count", sa.String(length=20), nullable=True),
        sa.Column("q2_overall_progress", sa.String(length=50), nullable=True),
        sa.Column("q3_ready_independent", sa.String(length=50), nullable=True),
        sa.Column("q4_need_1on1", sa.String(length=50), nullable=True),
        sa.Column("q5_biggest_challenges", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("q6_daily_hours", sa.String(length=20), nullable=True),
        sa.Column("q7_meeting_goals", sa.String(length=30), nullable=True),
        sa.Column("q8_internship_rating", sa.String(length=50), nullable=True),
        sa.Column("q9_tech_stack_comfort", sa.String(length=50), nullable=True),
        sa.Column("q10_docs_rating", sa.String(length=50), nullable=True),
        sa.Column("q11_improvements", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("q12_overall_feeling", sa.String(length=50), nullable=True),
        sa.Column("q13_open_feedback", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
