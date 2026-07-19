"""
Documents router — /api/v1/documents/*

Integrations:
  - File upload with validation (PDF, DOCX, TXT, PNG, JPG; max 50 MB).
  - Text extraction via document_service (calls AI service or runs locally).
  - Qdrant vector ingestion via vector_service (paragraph-aware chunking,
    nomic-embed-text embeddings, multi-tenant storage keyed by user_id).
  - Document listing and deletion (removes file, Qdrant vectors, and DB row).
"""
import uuid
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.auth.security.dependencies import get_current_user
from app.models.document import Document
from app.models.chat import ChatSession
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.storage_service import delete_file, save_file
from app.config import settings

from app.ai.client import AIClient, get_ai_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "image/png": "png",
    "image/jpeg": "jpg",
}




@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    session_id: uuid.UUID | None = None,
    use_rag: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client),
):
    """
    Upload a document. Text extraction and Qdrant vector ingestion run in the
    background so the API returns 202 Accepted immediately.

    Check the `processed` field on subsequent GET requests to know when
    embedding generation has finished and the document is searchable via RAG.
    """
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}",
        )

    contents = await file.read()
    if len(contents) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {settings.max_upload_size_mb} MB)"
        )

    if session_id:
        # Verify the session exists and belongs to the authenticated user.
        session_result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == current_user.id
            )
        )
        if not session_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Chat session not found")

    storage_path = await save_file(contents, file.filename, current_user.id)
    file_type = ALLOWED_TYPES[file.content_type]

    existing_result = await db.execute(
        select(Document)
        .where(
            Document.user_id == current_user.id,
            Document.filename == file.filename,
        )
        .order_by(Document.version.desc())
    )

    latest_document = existing_result.scalars().first()

    version = 1

    if latest_document:
        version = latest_document.version + 1

    doc = Document(
        user_id=current_user.id,
        session_id=session_id,
        filename=file.filename,
        file_type=file_type,
        file_size=len(contents),
        storage_path=storage_path,
        version=version,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Fire-and-forget: extract text, embed, and store in Qdrant (if use_rag is True).
    background_tasks.add_task(
        _process_document, doc.id, storage_path, current_user.id, file.filename, session_id, ai_client, use_rag
    )

    return doc


async def _process_document(
    document_id: uuid.UUID,
    storage_path: str,
    user_id: uuid.UUID,
    filename: str,
    session_id: uuid.UUID | None = None,
    ai_client: AIClient | None = None,
    use_rag: bool = True,
) -> None:
    """
    Background task: extract plain text from the uploaded file and ingest it
    into Qdrant (paragraph-chunked, nomic-embed-text embeddings).

    On success  → sets Document.processed = True.
    On failure  → logs the error; document stays as processed = False so the
                  caller can retry or surface an error in the UI.
    """
    if ai_client is None:
        ai_client = get_ai_client()
    async with AsyncSessionLocal() as db:
        try:
            # Fetch the document row.
            result_doc = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result_doc.scalar_one_or_none()
            if not doc:
                return

            print(f"\n[Ingestion] >>> Starting processing for file: '{filename}' (ID: {document_id})")
            print(f"[Ingestion] Extracting text content from '{filename}' ({doc.file_type})...")
            text = await ai_client.extract_text(storage_path, doc.file_type)

            if not use_rag:
                print(f"[Ingestion] Direct LLM mode: skipping Qdrant indexing for '{filename}'")
                logger.info(
                    "Document %s: Skipping vector indexing (Direct LLM mode).", document_id
                )
            elif not text.strip():
                print(f"[Ingestion] Warning: Extracted text is empty for '{filename}'")
                logger.warning(
                    "Document %s produced empty text — skipping vector storage.", document_id
                )
            else:
                # Chunk, embed, and store in Qdrant (multi-tenant, keyed by user_id).
                print(f"[Ingestion] Chunking, embedding, and storing text for '{filename}'...")
                try:
                    chunks_stored = await ai_client.store_document_vectors(
                        user_id=user_id,
                        document_id=document_id,
                        text=text,
                        filename=filename,
                        session_id=session_id,
                    )
                    print(f"[Ingestion] Successfully stored {chunks_stored} text chunks in Qdrant.")
                    logger.info(
                        "Document %s: %d chunks stored in Qdrant.", document_id, chunks_stored
                    )
                except Exception as qdrant_exc:
                    print(f"[Ingestion] Qdrant storage failed or skipped: {qdrant_exc}")
                    logger.warning(
                        "Qdrant storage failed for document %s: %s. Continuing processing.",
                        document_id,
                        qdrant_exc,
                    )

            # Vision RAG processing for images/PDFs
            if use_rag and settings.enable_vision_rag:
                try:
                    import base64
                    import httpx
                    import os
                    import tempfile
                    from pathlib import Path

                    is_url = storage_path.startswith("http://") or storage_path.startswith("https://")
                    local_pdf_path = ""
                    temp_file_path = None

                    if is_url:
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(storage_path)
                            resp.raise_for_status()
                            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{doc.file_type}")
                            temp_file.write(resp.content)
                            temp_file.close()
                            temp_file_path = temp_file.name
                            local_pdf_path = temp_file_path
                    else:
                        local_pdf_path = str(Path("uploads") / storage_path)

                    visuals = []
                    if doc.file_type == "pdf":
                        visuals = await ai_client.extract_visuals_from_pdf(local_pdf_path)
                    elif doc.file_type in ("png", "jpg", "jpeg"):
                        if temp_file_path:
                            img_bytes = Path(temp_file_path).read_bytes()
                        else:
                            img_bytes = Path(local_pdf_path).read_bytes()

                        b64_str = await ai_client.compress_image(img_bytes)
                        visuals = [{"base64_image": b64_str, "page_number": 1}]

                    if temp_file_path and os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)

                    if visuals:
                        print(f"[Ingestion] Document '{filename}' contains visual elements. Starting Vision RAG pipeline...")
                        images_stored = await ai_client.store_image_vectors(
                            user_id=user_id,
                            document_id=document_id,
                            filename=filename,
                            image_metadata=visuals,
                            session_id=session_id,
                        )
                        print(f"[Ingestion] Successfully processed and stored visual description for '{filename}' ({images_stored} pages).")
                        logger.info(
                            "Document %s: %d image descriptions stored in Qdrant.",
                            document_id,
                            images_stored,
                        )
                except Exception as vision_exc:
                    print(f"[Ingestion] Vision processing failed for document '{filename}': {vision_exc}")
                    logger.error(
                        "Vision processing failed for document %s: %s",
                        document_id,
                        vision_exc,
                        exc_info=True,
                    )

            # Mark the document as ready for RAG queries.
            doc.processed = True
            await db.commit()
            print(f"[Ingestion] <<< Finished processing for file: '{filename}' (ID: {document_id})\n")

        except Exception as exc:
            logger.error(
                "Document processing failed for %s: %s", document_id, exc, exc_info=True
            )


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all documents belonging to the current authenticated user."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download or stream the file content.
    For Cloudinary, redirects to the secure URL.
    For local files, returns a FileResponse.
    """
    import os
    from fastapi.responses import FileResponse, RedirectResponse

    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.storage_path.startswith("http://") or doc.storage_path.startswith("https://"):
        return RedirectResponse(doc.storage_path)

    file_path = os.path.join("uploads", doc.storage_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=file_path,
        filename=doc.filename,
        media_type="application/octet-stream"
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client),
):
    """
    Download or stream the file content.
    For Cloudinary, redirects to the secure URL.
    For local files, returns a FileResponse.
    """
    import os
    from fastapi.responses import FileResponse, RedirectResponse

    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 1. Remove the physical file from local storage / S3.
    await delete_file(doc.storage_path)

    # 2. Remove all Qdrant vectors associated with this document and user.
    await ai_client.delete_document_vectors(current_user.id, document_id)

    # 3. Remove the metadata row from PostgreSQL.
    await db.delete(doc)
    await db.commit()

@router.patch("/{document_id}/processed")
async def mark_document_processed(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )

    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    doc.processed = True

    await db.commit()

    return {
        "status": "completed",
        "document_id": str(document_id),
    }
