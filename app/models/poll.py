import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PollResponse(Base):
    __tablename__ = "poll_responses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Section 1 — Progress
    q1_modules_count: Mapped[str | None] = mapped_column(
        String(20)
    )  # "1","2","3-4","5+"
    q2_overall_progress: Mapped[str | None] = mapped_column(
        String(50)
    )  # excellent/good/average/slow/struggling

    # Section 2 — Independence & Support
    q3_ready_independent: Mapped[str | None] = mapped_column(
        String(50)
    )  # fully-ready/mostly-ready/partially-ready/not-yet
    q4_need_1on1: Mapped[str | None] = mapped_column(
        String(50)
    )  # yes-regularly/sometimes/rarely/no
    q5_biggest_challenges: Mapped[list[str] | None] = mapped_column(
        ARRAY(String)
    )  # multi-select

    # Section 3 — Time & Commitment
    q6_daily_hours: Mapped[str | None] = mapped_column(
        String(20)
    )  # <1h/1-2h/2-4h/4-6h/>6h
    q7_meeting_goals: Mapped[str | None] = mapped_column(
        String(30)
    )  # always/mostly/sometimes/rarely

    # Section 4 — Internship Experience
    q8_internship_rating: Mapped[str | None] = mapped_column(
        String(50)
    )  # excellent/very-good/good/average/below-avg/poor
    q9_tech_stack_comfort: Mapped[str | None] = mapped_column(
        String(50)
    )  # very-comfortable/comfortable-most/learning-as-i-go/...
    q10_docs_rating: Mapped[str | None] = mapped_column(
        String(50)
    )  # excellent/good/average/poor/needs-work
    q11_improvements: Mapped[list[str] | None] = mapped_column(
        ARRAY(String)
    )  # multi-select
    q12_overall_feeling: Mapped[str | None] = mapped_column(
        String(50)
    )  # very-motivated/positive/okay/overwhelmed/discouraged

    # Section 5 — Open feedback
    q13_open_feedback: Mapped[str | None] = mapped_column(Text)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
