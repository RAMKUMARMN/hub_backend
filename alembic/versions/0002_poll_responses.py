"""Add poll_responses table

Revision ID: 0002_poll_responses
Revises: 0001_initial
Create Date: 2026-05-24 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_poll_responses"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "poll_responses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Section 1
        sa.Column("q1_modules_count", sa.String(20), nullable=True),
        sa.Column("q2_overall_progress", sa.String(50), nullable=True),
        # Section 2
        sa.Column("q3_ready_independent", sa.String(50), nullable=True),
        sa.Column("q4_need_1on1", sa.String(50), nullable=True),
        sa.Column("q5_biggest_challenges", postgresql.ARRAY(sa.String), nullable=True),
        # Section 3
        sa.Column("q6_daily_hours", sa.String(20), nullable=True),
        sa.Column("q7_meeting_goals", sa.String(30), nullable=True),
        # Section 4
        sa.Column("q8_internship_rating", sa.String(50), nullable=True),
        sa.Column("q9_tech_stack_comfort", sa.String(50), nullable=True),
        sa.Column("q10_docs_rating", sa.String(50), nullable=True),
        sa.Column("q11_improvements", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("q12_overall_feeling", sa.String(50), nullable=True),
        # Section 5
        sa.Column("q13_open_feedback", sa.Text, nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("poll_responses")
