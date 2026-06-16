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
from app.services.document_service import extract_text
from app.services.storage_service import UPLOAD_DIR, delete_file, save_file
from app.services.vector_service import delete_document_vectors, store_document_vectors

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "image/png": "png",
    "image/jpeg": "jpg",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    session_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
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
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

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

    doc = Document(
        user_id=current_user.id,
        session_id=session_id,
        filename=file.filename,
        file_type=file_type,
        file_size=len(contents),
        storage_path=storage_path,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Fire-and-forget: extract text, embed, and store in Qdrant.
    background_tasks.add_task(
        _process_document, doc.id, storage_path, current_user.id, file.filename, session_id
    )

    return doc


async def _process_document(
    document_id: uuid.UUID,
    storage_path: str,
    user_id: uuid.UUID,
    filename: str,
    session_id: uuid.UUID | None = None,
) -> None:
    """
    Background task: extract plain text from the uploaded file and ingest it
    into Qdrant (paragraph-chunked, nomic-embed-text embeddings).

    On success  → sets Document.processed = True.
    On failure  → logs the error; document stays as processed = False so the
                  caller can retry or surface an error in the UI.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Fetch the document row.
            result_doc = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result_doc.scalar_one_or_none()
            if not doc:
                return

            # Extract plain text from the physical file.
            absolute_path = str(UPLOAD_DIR.resolve() / storage_path)
            text = await extract_text(absolute_path, doc.file_type)

            if not text.strip():
                logger.warning(
                    "Document %s produced empty text — skipping vector storage.", document_id
                )
            else:
                # Chunk, embed, and store in Qdrant (multi-tenant, keyed by user_id).
                chunks_stored = await store_document_vectors(
                    user_id=user_id,
                    document_id=document_id,
                    text=text,
                    filename=filename,
                    session_id=session_id,
                )
                logger.info(
                    "Document %s: %d chunks stored in Qdrant.", document_id, chunks_stored
                )

            # Mark the document as ready for RAG queries.
            doc.processed = True
            await db.commit()

        except Exception as exc:
            logger.error(
                "Document processing failed for %s: %s", document_id, exc, exc_info=True
            )


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    await delete_document_vectors(current_user.id, document_id)

    # 3. Remove the metadata row from PostgreSQL.
    await db.delete(doc)
    await db.commit()
