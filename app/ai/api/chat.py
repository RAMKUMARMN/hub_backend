"""
Chat router — /api/v1/chat/*

Integrations:
  - LLM streaming via app.ai (Ollama under the hood)
  - Qdrant vector search (via app.ai.search_relevant_chunks)
  - Source citations: first SSE event when use_rag=True
  - DeepSeek-R1 thinking stream: tokens inside <think>...</think> are streamed
    with {"thinking": token} instead of {"delta": token}
  - Context window summarization: once a session exceeds 10 messages, a
    background task asks the LLM to summarize history. Older messages are
    replaced with the summary injected into the system prompt.
  - Full chat history is persisted in PostgreSQL (chat_messages table).
"""
from __future__ import annotations

import json
import logging
import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.auth.security.dependencies import get_current_user
from app.models.chat import ChatMessage, ChatSession
from app.models.document import Document
from app.models.user import User
from app.schemas.chat import (
    CreateSessionRequest,
    MessageResponse,
    SendMessageRequest,
    SessionResponse,
)
from app.ai.client import AIClient, get_ai_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

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
    # Verify the session belongs to the authenticated user.
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


# ---------------------------------------------------------------------------
# Context-window summarization background task
# ---------------------------------------------------------------------------

async def _summarize_and_prune(session_id: uuid.UUID, ai_client: AIClient) -> None:
    """
    Background task: triggered when a session exceeds 10 messages.

    1. Fetches all but the last 4 messages.
    2. Asks the LLM to produce a 3-sentence summary of the older messages.
    3. Stores the summary in ChatSession.summary.
    4. Deletes the older messages to keep the database lean.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Fetch only active (unsummarized) messages ordered by time.
            active_msgs_result = await db.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.session_id == session_id,
                    ChatMessage.is_summarized == False
                )
                .order_by(ChatMessage.created_at.asc())
            )
            active_msgs = active_msgs_result.scalars().all()

            # Keep the last 4 active messages; summarize the rest.
            to_summarize = active_msgs[:-4]
            if not to_summarize:
                return

            history_text = "\n".join(
                f"{m.role.upper()}: {m.content}" for m in to_summarize
            )

            # Retrieve previous summary to merge if it exists
            sess_result = await db.execute(
                select(ChatSession).where(ChatSession.id == session_id)
            )
            session = sess_result.scalar_one_or_none()

            if session and session.summary:
                merge_text = (
                    f"Previous conversation summary: {session.summary}\n\n"
                    f"New conversation segment:\n{history_text}"
                )
                summary_text = await ai_client.summarize_text(merge_text)
            else:
                summary_text = await ai_client.summarize_text(history_text)

            # Save the new rolling summary and mark messages as summarized
            if session and summary_text:
                session.summary = summary_text
                for msg in to_summarize:
                    msg.is_summarized = True
                await db.commit()

            logger.info(
                "Summarized and pruned %d messages for session %s.",
                len(to_summarize),
                session_id,
            )
        except Exception as exc:
            logger.error(
                "Context summarization failed for session %s: %s",
                session_id,
                exc,
                exc_info=True,
            )


# ---------------------------------------------------------------------------
# Main streaming message endpoint
# ---------------------------------------------------------------------------

async def _process_chat_message_and_stream(
    session_id: uuid.UUID,
    current_user: User,
    content: str,
    use_rag: bool,
    thinking_mode: bool,
    retrieval_mode: str,
    rag_chunk_limit: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
    ai_client: AIClient,
    document_ids: list[uuid.UUID] | None = None,
) -> StreamingResponse:
    """
    Core messaging and streaming logic shared between POST and GET endpoints.
    """
    # 1. Verify the session belongs to the authenticated user.
    sess_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == current_user.id
        )
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. Persist the user's message.
    user_msg = ChatMessage(
        session_id=session_id, role="user", content=content
    )
    db.add(user_msg)
    await db.commit()

    # 3. Build chat history: last 10 messages (oldest first) that are not summarized.
    history_result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.session_id == session_id,
            ChatMessage.is_summarized == False
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    chat_history = [
        {"role": m.role, "content": m.content}
        for m in reversed(history_result.scalars().all())
    ]

    # 4. Count active (unsummarized) messages to decide if summarization should be triggered.
    msg_count_result = await db.execute(
        select(func.count()).where(
            ChatMessage.session_id == session_id,
            ChatMessage.is_summarized == False
        )
    )
    total_msg_count = msg_count_result.scalar_one()

    # 5. Build the system prompt.
    # Prepend any existing session summary for context window management.
    if session.summary:
        system_instruction = (
            "You are a helpful college assistant. "
            "Here is a summary of the earlier parts of this conversation:\n"
            f"{session.summary}\n\n"
            "Continue the conversation based on the messages below."
        )
    else:
        system_instruction = "You are a helpful college assistant for TKM college students."

    # 6. RAG context injection — search Qdrant for relevant document chunks.
    matching_data: list[dict] = []
    if use_rag:
        try:
            # Retrieve processed documents that belong to current user
            # AND are either global (session_id IS NULL) OR belong to current session.
            # This is the security boundary — documents from other sessions are never included.
            allowed_docs_result = await db.execute(
                select(Document.id).where(
                    Document.user_id == current_user.id,
                    Document.processed == True,
                    (Document.session_id == None) | (Document.session_id == session_id),
                )
            )
            allowed_doc_ids = [row[0] for row in allowed_docs_result.all()]

            # If the user has selected specific documents, restrict to their selection.
            # We intersect with allowed_doc_ids so that cross-session documents
            # provided by the user are silently ignored — they will never appear.
            if document_ids is not None:
                allowed_set = set(allowed_doc_ids)
                allowed_doc_ids = [d for d in document_ids if d in allowed_set]

            matching_data = await ai_client.search_relevant_chunks(
                user_id=current_user.id,
                query=content,
                limit=rag_chunk_limit,
                retrieval_mode=retrieval_mode,
                allowed_document_ids=allowed_doc_ids,
                session_id=session_id,
                selected_document_ids=document_ids,
            )
        except httpx.ConnectError:
            logger.warning("Qdrant unavailable during RAG search for user %s.", current_user.id)

        if matching_data:
            context = "\n\n".join(item["text"] for item in matching_data)
            system_instruction = (
                "You are an assistant answering questions using the following document context.\n"
                "Answer based on the context. If the context does not contain the answer, "
                "say so clearly but still try to help based on general knowledge.\n\n"
                f"--- DOCUMENT CONTEXT ---\n{context}\n------------------------"
            )
            if session.summary:
                system_instruction += (
                    f"\n\n--- CONVERSATION SUMMARY ---\n{session.summary}\n----------------------------"
                )

    # 6.5. Inject thinking mode instruction.
    if thinking_mode:
        system_instruction += (
            "\n\nYou may think step by step and output your reasoning inside <think>...</think> tags before answering."
        )
    else:
        system_instruction += (
            "\n\nRespond directly. Do not output any reasoning or step-by-step thinking, and do not use <think> tags."
        )

    # 7. Assemble the full message list for the LLM.
    ollama_messages = [
        {"role": "system", "content": system_instruction}
    ] + chat_history

    # Capture ids needed inside the async generator closure.
    _session_id = session_id

    async def event_generator():
        full_response = ""

        # A. Emit source citations as the very first SSE event (RAG only).
        if matching_data:
            yield f"data: {json.dumps({'sources': matching_data})}\n\n"

        # B. Stream tokens from the AI module.
        is_thinking = False
        try:
            async for token in ai_client.chat_stream(ollama_messages):
                # Detect DeepSeek-R1 <think> reasoning block boundaries.
                if "<think>" in token:
                    is_thinking = True
                    token = token.replace("<think>", "")
                if "</think>" in token:
                    is_thinking = False
                    token = token.replace("</think>", "")

                if token:
                    full_response += token
                    if is_thinking:
                        # Stream thinking tokens with a separate key so
                        # the frontend can render them differently.
                        yield f"data: {json.dumps({'thinking': token})}\n\n"
                    else:
                        yield f"data: {json.dumps({'delta': token})}\n\n"

        except httpx.ConnectError:
            error_msg = (
                "The AI model is currently unavailable. "
                "Please ensure Ollama is running locally."
            )
            yield f"data: {json.dumps({'delta': error_msg})}\n\n"
            full_response = error_msg
        except httpx.HTTPStatusError as exc:
            error_msg = f"AI service error ({exc.response.status_code}). Please try again."
            yield f"data: {json.dumps({'delta': error_msg})}\n\n"
            full_response = error_msg

        # C. Persist the completed assistant message.
        async with AsyncSessionLocal() as write_db:
            assistant_msg = ChatMessage(
                session_id=_session_id,
                role="assistant",
                content=full_response,
            )
            write_db.add(assistant_msg)
            await write_db.commit()

        yield "data: [DONE]\n\n"

    # 8. After streaming, schedule summarization if the session has grown long.
    if total_msg_count > 10:
        background_tasks.add_task(_summarize_and_prune, _session_id, ai_client)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client),
):
    """
    Send a user message and stream the AI response as Server-Sent Events (POST route).
    """
    return await _process_chat_message_and_stream(
        session_id=session_id,
        current_user=current_user,
        content=body.content,
        use_rag=body.use_rag,
        thinking_mode=body.thinking_mode,
        retrieval_mode=body.retrieval_mode,
        rag_chunk_limit=body.rag_chunk_limit,
        document_ids=body.document_ids,
        background_tasks=background_tasks,
        db=db,
        ai_client=ai_client,
    )


@router.get("/sessions/{session_id}/messages/stream")
async def stream_messages_get(
    session_id: uuid.UUID,
    content: str,
    token: str,
    background_tasks: BackgroundTasks,
    use_rag: bool = False,
    thinking_mode: bool = True,
    retrieval_mode: str = "semantic",
    rag_chunk_limit: int = 4,
    document_ids: str | None = None,
    db: AsyncSession = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client),
):
    """
    Send a user message and stream the AI response as Server-Sent Events (GET route for EventSource compatibility).
    """
    # 1. Authenticate user from the token passed as query parameter
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        from app.auth.security.jwt import decode_token
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exception
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        current_user_id = uuid.UUID(user_id)
    except Exception:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == current_user_id))
    current_user = result.scalar_one_or_none()
    if current_user is None or not current_user.is_active:
        raise credentials_exception

    # Parse comma-separated document_ids string into a list of UUIDs (if provided).
    parsed_document_ids: list[uuid.UUID] | None = None
    if document_ids:
        try:
            parsed_document_ids = [uuid.UUID(d.strip()) for d in document_ids.split(",") if d.strip()]
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid document_ids format. Expected comma-separated UUIDs.")

    return await _process_chat_message_and_stream(
        session_id=session_id,
        current_user=current_user,
        content=content,
        use_rag=use_rag,
        thinking_mode=thinking_mode,
        retrieval_mode=retrieval_mode,
        rag_chunk_limit=rag_chunk_limit,
        document_ids=parsed_document_ids,
        background_tasks=background_tasks,
        db=db,
        ai_client=ai_client,
    )
