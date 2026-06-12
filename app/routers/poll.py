"""Poll router — /api/v1/poll/*

Public endpoint: POST /api/v1/poll/submit  (no auth required — anonymous)
Admin endpoint:  GET  /api/v1/poll/results  (admin auth required)
Admin endpoint:  GET  /api/v1/poll/responses (admin auth required — raw list)
"""
from collections import Counter

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.poll import PollResponse
from app.models.user import User
from app.schemas.poll import PollResponseOut, PollSummary, SubmitPollRequest

router = APIRouter(prefix="/poll", tags=["poll"])


# ── Public: submit a response (no auth — anonymous poll) ──────────────────────
@router.post(
    "/submit",
    response_model=PollResponseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit intern pulse-check response (anonymous)",
)
async def submit_poll(
    body: SubmitPollRequest,
    db: AsyncSession = Depends(get_db),
):
    row = PollResponse(**body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ── Admin: aggregated summary ─────────────────────────────────────────────────
@router.get(
    "/results",
    response_model=PollSummary,
    summary="Get aggregated poll results (admin only)",
)
async def get_poll_results(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(select(PollResponse))
    rows: list[PollResponse] = result.scalars().all()

    def _tally(field: str) -> dict[str, int]:
        return dict(Counter(getattr(r, field) for r in rows if getattr(r, field)))

    def _tally_array(field: str) -> dict[str, int]:
        c: Counter = Counter()
        for r in rows:
            values = getattr(r, field) or []
            c.update(values)
        return dict(c)

    return PollSummary(
        total_responses=len(rows),
        q1_modules_count=_tally("q1_modules_count"),
        q2_overall_progress=_tally("q2_overall_progress"),
        q3_ready_independent=_tally("q3_ready_independent"),
        q4_need_1on1=_tally("q4_need_1on1"),
        q5_biggest_challenges=_tally_array("q5_biggest_challenges"),
        q6_daily_hours=_tally("q6_daily_hours"),
        q7_meeting_goals=_tally("q7_meeting_goals"),
        q8_internship_rating=_tally("q8_internship_rating"),
        q9_tech_stack_comfort=_tally("q9_tech_stack_comfort"),
        q10_docs_rating=_tally("q10_docs_rating"),
        q11_improvements=_tally_array("q11_improvements"),
        q12_overall_feeling=_tally("q12_overall_feeling"),
        open_feedback=[r.q13_open_feedback for r in rows if r.q13_open_feedback],
    )


# ── Admin: raw list ───────────────────────────────────────────────────────────
@router.get(
    "/responses",
    response_model=list[PollResponseOut],
    summary="Get all raw poll responses (admin only)",
)
async def list_poll_responses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(
        select(PollResponse).order_by(PollResponse.submitted_at.desc())
    )
    return result.scalars().all()
