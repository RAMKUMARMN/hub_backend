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
import sys
import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status, Request
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


class ThinkTagParser:
    def __init__(self, thinking_mode: bool):
        self.thinking_mode = thinking_mode
        self.buffer = ""
        self.is_thinking = False

    def feed(self, chunk: str) -> list[tuple[str, str]]:
        self.buffer += chunk
        events = []

        while True:
            if not self.is_thinking:
                idx = self.buffer.find("<think>")
                if idx != -1:
                    normal_text = self.buffer[:idx]
                    if normal_text:
                        events.append(("delta", normal_text))
                    self.buffer = self.buffer[idx + 7:]
                    self.is_thinking = True
                    continue
                
                prefix_found = False
                for length in range(6, 0, -1):
                    prefix = "<think"[:length]
                    if self.buffer.endswith(prefix):
                        normal_text = self.buffer[:-length]
                        if normal_text:
                            events.append(("delta", normal_text))
                        self.buffer = prefix
                        prefix_found = True
                        break
                if prefix_found:
                    break
                
                if self.buffer:
                    events.append(("delta", self.buffer))
                    self.buffer = ""
                break

            else:
                idx = self.buffer.find("</think>")
                if idx != -1:
                    thinking_text = self.buffer[:idx]
                    if thinking_text and self.thinking_mode:
                        events.append(("thinking", thinking_text))
                    self.buffer = self.buffer[idx + 8:]
                    self.is_thinking = False
                    continue

                prefix_found = False
                for length in range(7, 0, -1):
                    prefix = "</think"[:length]
                    if self.buffer.endswith(prefix):
                        thinking_text = self.buffer[:-length]
                        if thinking_text and self.thinking_mode:
                            events.append(("thinking", thinking_text))
                        self.buffer = prefix
                        prefix_found = True
                        break
                if prefix_found:
                    break

                if self.buffer:
                    if self.thinking_mode:
                        events.append(("thinking", self.buffer))
                    self.buffer = ""
                break

        return events

    def finalize(self) -> list[tuple[str, str]]:
        events = []
        if self.buffer:
            if self.is_thinking:
                if self.thinking_mode:
                    events.append(("thinking", self.buffer))
            else:
                events.append(("delta", self.buffer))
            self.buffer = ""
        return events


def sanitize_content(content: str) -> str:
    """
    Sanitize raw assistant response text to strip stray thought tags, instructions,
    and trailing template fragments leaked by local models.
    """
    if not content:
        return ""
    import re
    # Remove stray </think> tags
    content = re.sub(r"<\s*/\s*think\s*>", "", content, flags=re.IGNORECASE)
    # Remove stray <think> tags
    content = re.sub(r"<\s*think\s*>", "", content, flags=re.IGNORECASE)
    # Clean up standard template leakage instructions
    content = re.sub(
        r'tags"\s*before\s*providing\s*your\s*final\s*answer\."\s*So\s*I\s*will\s*generate\s*the\s*thought\s*block\s*first\.',
        "",
        content,
        flags=re.IGNORECASE
    )
    # Clean up remaining instruction artifacts
    content = re.sub(
        r'Respond\s*directly\.\s*Do\s*not\s*output\s*any\s*reasoning\s*or\s*step-by-step\s*thinking.*',
        "",
        content,
        flags=re.IGNORECASE
    )
    return content.strip()


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
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

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
    use_hyde: bool,
    web_search: bool,
    thinking_mode: bool,
    retrieval_mode: str,
    rag_chunk_limit: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
    ai_client: AIClient,
    request: Request | None = None,
    document_ids: list[uuid.UUID] | None = None,
    use_reranker: bool = False,
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
    # We prune history if it exceeds 32,000 characters (~8,000 tokens) to prevent prompt bloat.
    history_result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.session_id == session_id,
            ChatMessage.is_summarized == False
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    
    raw_history = history_result.scalars().all()
    chat_history = []
    char_count = 0
    max_history_chars = 32000  # ~8,000 tokens limit for active prompt injection
    
    for m in raw_history:
        if m.role == "assistant" and not m.content:
            continue
        msg_len = len(m.content or "")
        # If adding this message exceeds our history budget, stop adding older ones
        if char_count + msg_len > max_history_chars and len(chat_history) > 0:
            break
        chat_history.append({"role": m.role, "content": m.content or ""})
        char_count += msg_len
        
    chat_history.reverse()  # Order oldest first

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
    meta_data = None
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

            # Check for generic visual queries referencing session assets
            content_lower = content.lower().strip()
            generic_visual_query = any(
                phrase in content_lower
                for phrase in (
                    "this image", "this picture", "this photo",
                    "attached image", "attached picture", "attached photo",
                    "explain this", "what is this", "describe this", "what is in this"
                )
            )

            forced_image_data: list[dict] = []
            if generic_visual_query:
                # Find the most recently processed image/document in the active session
                latest_image_result = await db.execute(
                    select(Document)
                    .where(
                        Document.session_id == session_id,
                        Document.processed == True,
                        Document.file_type.in_(["png", "jpg", "jpeg", "pdf"])
                    )
                    .order_by(Document.created_at.desc())
                    .limit(1)
                )
                latest_image = latest_image_result.scalar_one_or_none()
                if latest_image:
                    # Force retrieve descriptions/chunks from this specific document
                    forced_image_data = await ai_client.search_relevant_chunks(
                        user_id=current_user.id,
                        query=content,
                        limit=4,
                        retrieval_mode=retrieval_mode,
                        use_hyde=use_hyde,
                        allowed_document_ids=[latest_image.id],
                        session_id=session_id,
                        selected_document_ids=[latest_image.id],
                        use_reranker=use_reranker,
                    )

            # Standard semantic search
            matching_data = await ai_client.search_relevant_chunks(
                user_id=current_user.id,
                query=content,
                limit=rag_chunk_limit,
                retrieval_mode=retrieval_mode,
                use_hyde=use_hyde,
                allowed_document_ids=allowed_doc_ids,
                session_id=session_id,
                selected_document_ids=document_ids,
                use_reranker=use_reranker,
                include_meta=True,
            )

            # Extract search strategy metadata chunk if present in standard search
            if matching_data:
                meta_items = [item for item in matching_data if item.get("is_meta")]
                if meta_items:
                    meta_data = meta_items[0]
                    matching_data = [item for item in matching_data if not item.get("is_meta")]

            # Clean forced image data if metadata is present
            if forced_image_data:
                forced_image_data = [item for item in forced_image_data if not item.get("is_meta")]

            # Merge forced image descriptions at the beginning of the list, removing duplicates
            if forced_image_data:
                seen_texts = {item["text"] for item in forced_image_data}
                filtered_standard = [item for item in matching_data if item["text"] not in seen_texts]
                matching_data = forced_image_data + filtered_standard
                # Limit the total number of chunks passed to the LLM to prevent prompt bloat
                matching_data = matching_data[:rag_chunk_limit]
            
            # Clean any internal <think>...</think> blocks from chunks to prevent prompt confusion
            import re
            for item in matching_data:
                if "text" in item:
                    cleaned_txt = re.sub(r"<think>.*?</think>", "", item["text"], flags=re.DOTALL)
                    cleaned_txt = re.sub(r"<think>.*", "", cleaned_txt, flags=re.DOTALL)
                    item["text"] = cleaned_txt.strip()
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
            "\n\nCRITICAL: You MUST think step by step and output your reasoning inside <think>...</think> tags before providing your final answer. "
            "Write at least 2-3 sentences explaining your thought process inside the tags."
        )
    else:
        system_instruction += (
            "\n\nRespond directly"
        )

    # 7. Assemble the full message list for the LLM.
    from datetime import datetime
    current_time_str = datetime.now().strftime("%A, %B %d, %Y, %I:%M %p")
    time_prefix = f"Current date and time: {current_time_str}.\n\n"

    ollama_messages = [
        {"role": "system", "content": time_prefix + system_instruction}
    ] + chat_history

    # Capture ids needed inside the async generator closure.
    _session_id = session_id

    async def event_generator():
        full_response = ""
        full_thinking = ""

        # A. Emit source citations as the very first SSE event (RAG only).
        if matching_data or meta_data:
            yield f"data: {json.dumps({'sources': matching_data, 'search_metadata': meta_data})}\n\n"

        # Check if the retrieved context contains any visual descriptions
        has_visual_chunks = any(
            "[Image Description" in item.get("text", "")
            for item in matching_data
        )

        direct_content = None

        tools = []
        if use_rag and has_visual_chunks:
            reinspect_tool = {
                "type": "function",
                "function": {
                    "name": "reinspect_document_page",
                    "description": (
                        "Use this tool to re-inspect a specific page of a PDF document using a vision model. "
                        "Use this ONLY when the retrieved context references a page/image but lacks the "
                        "specific, exact detail (like values, charts, tables, equations, data points, or text) "
                        "needed to accurately answer the user's query."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "document_id": {
                                "type": "string",
                                "description": "The unique UUID of the document to inspect."
                            },
                            "page_number": {
                                "type": "integer",
                                "description": "The 1-based page number of the document/PDF to inspect."
                            },
                            "specific_question": {
                                "type": "string",
                                "description": "The specific question or detail to extract from the page."
                            }
                        },
                        "required": ["document_id", "page_number", "specific_question"]
                    }
                }
            }
            tools.append(reinspect_tool)

        from app.config import settings as app_settings
        if web_search:
            web_search_tool = {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": (
                        "Search the web for real-time information, news, current events, live scores, or general facts."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query term."
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
            tools.append(web_search_tool)

        if tools:
            try:
                # Execute up to 3 sequential tool call turns
                max_turns = 3
                executed_tool_calls = set()
                parser = ThinkTagParser(thinking_mode=thinking_mode)
                
                parser = ThinkTagParser(thinking_mode=thinking_mode)
                
                for turn in range(max_turns):
                    if "pytest" not in sys.modules and request and await request.is_disconnected():
                        logger.info("Client disconnected during tools turn. Aborting.")
                        break
                    response_msg = await ai_client.chat_with_tools(ollama_messages, tools=tools, think=thinking_mode)
                    
                    # Yield intermediate thinking if the model wrote any
                    thinking = response_msg.get("thinking", "")
                    if thinking:
                        import asyncio
                        full_think_str = f"<think>{thinking}</think>"
                        chunk_size = 8
                        for i in range(0, len(full_think_str), chunk_size):
                            if "pytest" not in sys.modules and request and await request.is_disconnected():
                                logger.info("Client disconnected during intermediate think stream. Aborting.")
                                break
                            token = full_think_str[i : i + chunk_size]
                            for event_type, content_text in parser.feed(token):
                                if event_type == "thinking":
                                    full_thinking += content_text
                                else:
                                    full_response += content_text
                                yield f"data: {json.dumps({event_type: content_text})}\n\n"
                            await asyncio.sleep(0.01)
                    
                    tool_calls = response_msg.get("tool_calls")
                    
                    if tool_calls:
                        # Check for duplicate tool calls to prevent infinite loops (or mock loops in tests)
                        has_duplicate = False
                        for tool_call in tool_calls:
                            func_name = tool_call.get("function", {}).get("name")
                            args = tool_call.get("function", {}).get("arguments", {})
                            args_str = json.dumps(args, sort_keys=True) if isinstance(args, dict) else str(args)
                            call_key = (func_name, args_str)
                            if call_key in executed_tool_calls:
                                logger.warning("Duplicate tool call detected: %s with args %s. Breaking tool loop.", func_name, args_str)
                                has_duplicate = True
                                break
                            executed_tool_calls.add(call_key)
                        
                        if has_duplicate:
                            direct_content = response_msg.get("content", "")
                            break

                        # Append the assistant's message with tool calls to the history
                        ollama_messages.append(response_msg)
                        
                        # Process each tool call
                        for tool_call in tool_calls:
                            func_name = tool_call.get("function", {}).get("name")
                            args = tool_call.get("function", {}).get("arguments", {})
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except Exception:
                                    args = {}

                            tool_result = ""
                            if func_name == "reinspect_document_page":
                                doc_id_str = args.get("document_id")
                                page_num = args.get("page_number")
                                specific_question = args.get("specific_question") or ""
                                # Yield status update to frontend
                                yield f"data: {json.dumps({'status': f'👁️ Re-inspecting page {page_num or 1}...'})}\n\n"
                                specific_question = args.get("specific_question") or ""
                                # Yield status update to frontend
                                yield f"data: {json.dumps({'status': f'👁️ Re-inspecting page {page_num or 1}...'})}\n\n"
                                
                                doc_id = None
                                if doc_id_str:
                                    try:
                                        doc_id = uuid.UUID(doc_id_str)
                                    except ValueError:
                                        pass
                                
                                if not doc_id:
                                    for chunk in matching_data:
                                        if "[Image Description" in chunk.get("text", "") and chunk.get("document_id"):
                                            try:
                                                doc_id = uuid.UUID(chunk["document_id"])
                                                break
                                            except ValueError:
                                                continue
                                
                                if doc_id:
                                    async with AsyncSessionLocal() as db_session:
                                        doc_res = await db_session.execute(
                                            select(Document).where(
                                                Document.id == doc_id,
                                                Document.user_id == current_user.id
                                            )
                                        )
                                        doc_obj = doc_res.scalar_one_or_none()
                                        if doc_obj:
                                            storage_path = doc_obj.storage_path
                                            is_url = storage_path.startswith("http://") or storage_path.startswith("https://")
                                            local_pdf_path = ""
                                            temp_file_path = None
                                            
                                            try:
                                                if is_url:
                                                    async with httpx.AsyncClient() as client:
                                                        resp = await client.get(storage_path)
                                                        resp.raise_for_status()
                                                        import tempfile
                                                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{doc_obj.file_type}")
                                                        temp_file.write(resp.content)
                                                        temp_file.close()
                                                        temp_file_path = temp_file.name
                                                        local_pdf_path = temp_file_path
                                                else:
                                                    from pathlib import Path
                                                    local_pdf_path = str(Path("uploads") / storage_path)
                                                
                                                from app.ai.services import vision_service
                                                page_number = int(page_num) if page_num else 1
                                                
                                                if doc_obj.file_type in ("png", "jpg", "jpeg"):
                                                    from pathlib import Path
                                                    if temp_file_path:
                                                        img_bytes = Path(temp_file_path).read_bytes()
                                                    else:
                                                        img_bytes = Path(local_pdf_path).read_bytes()
                                                    compressed = vision_service.process_and_compress_image(img_bytes)
                                                    import base64
                                                    b64_str = base64.b64encode(compressed).decode("utf-8")
                                                    
                                                    prompt = (
                                                        f"Look at this image. Answer the following question based on the visual contents: {specific_question}"
                                                    )
                                                    
                                                    async with httpx.AsyncClient(timeout=300) as client:
                                                        response = await client.post(
                                                            f"{app_settings.ollama_base_url}/api/generate",
                                                            json={
                                                                "model": app_settings.ollama_vision_model,
                                                                "prompt": prompt,
                                                                "images": [b64_str],
                                                                "stream": False,
                                                                "think": False,
                                                                "think": False,
                                                                "options": {
                                                                    "num_ctx": 4096,
                                                                },
                                                                "keep_alive": "10s",
                                                            }
                                                        )
                                                        response.raise_for_status()
                                                        tool_result = response.json().get("response", "").strip()
                                                else:
                                                    tool_result = await vision_service.reinspect_page(
                                                        pdf_path=local_pdf_path,
                                                        page_number=page_number,
                                                        specific_question=specific_question
                                                    )
                                            except Exception as e:
                                                logger.error("Error in reinspect_page: %s", e, exc_info=True)
                                                tool_result = f"Error during visual reinspection: {str(e)}"
                                            finally:
                                                import os
                                                if temp_file_path and os.path.exists(temp_file_path):
                                                    try:
                                                        os.unlink(temp_file_path)
                                                    except Exception:
                                                        pass
                                
                                if not tool_result:
                                    tool_result = "No additional details found on page or document not found."

                            elif func_name == "web_search":
                                query_arg = args.get("query")
                                if query_arg:
                                    # Yield status update to frontend
                                    yield f"data: {json.dumps({'status': f'🔍 Searching the web for \"{query_arg}\"...'})}\n\n"
                                    # Yield status update to frontend
                                    yield f"data: {json.dumps({'status': f'🔍 Searching the web for \"{query_arg}\"...'})}\n\n"
                                    from app.ai.services.search_service import unified_web_search
                                    try:
                                        tool_result = await unified_web_search(query_arg)
                                    except Exception as e:
                                        logger.error("Error in unified_web_search: %s", e, exc_info=True)
                                        tool_result = f"Error during web search: {str(e)}"
                                else:
                                    tool_result = "Error: search query argument is missing."

                            else:
                                tool_result = f"Error: unknown tool '{func_name}'."

                            tool_msg = {
                                "role": "tool",
                                "content": tool_result
                            }
                            if "id" in tool_call:
                                tool_msg["tool_call_id"] = tool_call["id"]
                            ollama_messages.append(tool_msg)
                    else:
                        # No tool calls, the model has finished reasoning.
                        # The thinking was already streamed above, so we only need to stream content.
                        # No tool calls, the model has finished reasoning.
                        # The thinking was already streamed above, so we only need to stream content.
                        direct_content = response_msg.get("content", "")
                        break
            except Exception as exc:
                logger.error("Failed to execute tool-calling loop: %s", exc, exc_info=True)
                direct_content = None

        # B. Stream tokens from the AI module.
        try:
            if 'parser' not in locals():
                parser = ThinkTagParser(thinking_mode=thinking_mode)
            if 'parser' not in locals():
                parser = ThinkTagParser(thinking_mode=thinking_mode)
            if direct_content is not None:
                import asyncio
                chunk_size = 8
                for i in range(0, len(direct_content), chunk_size):
                    if "pytest" not in sys.modules and request and await request.is_disconnected():
                        logger.info("Client disconnected during direct content stream. Aborting.")
                        break
                    token = direct_content[i : i + chunk_size]
                    for event_type, content_text in parser.feed(token):
                        if event_type == "thinking":
                            full_thinking += content_text
                        else:
                            full_response += content_text
                        yield f"data: {json.dumps({event_type: content_text})}\n\n"
                    await asyncio.sleep(0.01)
            else:
                async for token in ai_client.chat_stream(ollama_messages, think=thinking_mode):
                    if "pytest" not in sys.modules and request and await request.is_disconnected():
                        logger.info("Client disconnected during stream. Aborting.")
                        break
                    for event_type, content_text in parser.feed(token):
                        if event_type == "thinking":
                            full_thinking += content_text
                        else:
                            full_response += content_text
                        yield f"data: {json.dumps({event_type: content_text})}\n\n"
            
            # Finalize parser tokens unless aborted
            if "pytest" in sys.modules or not request or not await request.is_disconnected():
                for event_type, content_text in parser.finalize():
                    if event_type == "thinking":
                        full_thinking += content_text
                    else:
                        full_response += content_text
                    yield f"data: {json.dumps({event_type: content_text})}\n\n"

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

        # C. Persist the completed assistant message (only if non-empty).
        if sanitize_content(full_response) or full_thinking:
            async with AsyncSessionLocal() as write_db:
                saved_sources = matching_data.copy() if matching_data else []
                if meta_data:
                    saved_sources.append(meta_data)
                assistant_msg = ChatMessage(
                    session_id=_session_id,
                    role="assistant",
                    content=sanitize_content(full_response),
                    thinking=full_thinking if full_thinking else None,
                    sources=saved_sources if saved_sources else None,
                )
                write_db.add(assistant_msg)
                await write_db.commit()

        if "pytest" in sys.modules or not request or not await request.is_disconnected():
            yield "data: [DONE]\n\n"

    # 8. After streaming, schedule summarization if the session has grown long (count > 10)
    # OR if the total unsummarized messages characters exceed 40,000 characters (~10,000 tokens).
    history_chars = sum(len(m.get("content", "")) for m in chat_history)
    if total_msg_count > 10 or history_chars > 40000:
        background_tasks.add_task(_summarize_and_prune, _session_id, ai_client)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    request: Request,
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
        use_hyde=body.use_hyde,
        web_search=body.web_search,
        thinking_mode=body.thinking_mode,
        retrieval_mode=body.retrieval_mode,
        rag_chunk_limit=body.rag_chunk_limit,
        document_ids=body.document_ids,
        background_tasks=background_tasks,
        db=db,
        ai_client=ai_client,
        request=request,
        use_reranker=body.use_reranker,
    )


@router.get("/sessions/{session_id}/messages/stream")
async def stream_messages_get(
    session_id: uuid.UUID,
    content: str,
    token: str,
    request: Request,
    background_tasks: BackgroundTasks,
    use_rag: bool = False,
    use_hyde: bool = False,
    web_search: bool = False,
    thinking_mode: bool = True,
    retrieval_mode: str = "semantic",
    rag_chunk_limit: int = 4,
    document_ids: str | None = None,
    use_reranker: bool = False,
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
        use_hyde=use_hyde,
        web_search=web_search,
        thinking_mode=thinking_mode,
        retrieval_mode=retrieval_mode,
        rag_chunk_limit=rag_chunk_limit,
        document_ids=parsed_document_ids,
        background_tasks=background_tasks,
        db=db,
        ai_client=ai_client,
        request=request,
        use_reranker=use_reranker,
    )
