"""
Chat router — /api/v1/chat/*

Students: implement the streaming message endpoint (POST /sessions/{id}/messages).
"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.security.dependencies import get_current_user
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.chat import (
    CreateSessionRequest,
    MessageResponse,
    SendMessageRequest,
    SessionResponse,
)
from app.services.llm_service import chat_stream

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = ChatSession(user_id=current_user.id, title=body.title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    return result.scalars().all()


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify session belongs to user
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == current_user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    msgs = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return msgs.scalars().all()


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a user message and stream the AI response as Server-Sent Events.

    Response format (SSE):
      data: {"delta": "token"}
      data: [DONE]

    TODO:
      1. Verify session belongs to current_user.
      2. Save the user message to chat_messages table.
      3. Retrieve last 10 messages as context for Ollama.
      4. If body.use_rag is True, call retrieve_chunks() and pass to chat_stream().
      5. Stream tokens from chat_stream(), yielding SSE events.
      6. After streaming completes, save the full assistant response to chat_messages.
    """

    async def event_generator():
        full_response = ""

        # Save user message
        user_msg = ChatMessage(session_id=session_id, role="user", content=body.content)
        db.add(user_msg)
        await db.commit()

        # Build message history for context
        history_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(10)
        )
        history = [
            {"role": m.role, "content": m.content}
            for m in reversed(history_result.scalars().all())
        ]

        # Stream from AI service (RAG retrieval happens inside the AI service)
        async for token in chat_stream(
            history,
            user_id=str(current_user.id),
            use_rag=body.use_rag,
        ):
            full_response += token
            yield f"data: {json.dumps({'delta': token})}\n\n"

        # Save assistant message after streaming completes
        assistant_msg = ChatMessage(
            session_id=session_id, role="assistant", content=full_response
        )
        db.add(assistant_msg)
        await db.commit()

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
