"""
Documents router — /api/v1/documents/*

Students: implement the upload endpoint to trigger async text extraction + RAG ingestion.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.document_service import extract_text
from app.services.rag_service import delete_document_chunks, ingest_document
from app.services.storage_service import UPLOAD_DIR, delete_file, save_file
from app.queue.producer import publish_job
from app.queue.schemas import Job, JobType

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document. Text extraction and RAG ingestion run in the background.

    Returns 202 immediately — check `processed` field later to see when done.
    """
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    storage_path = await save_file(contents, file.filename, current_user.id)
    file_type = ALLOWED_TYPES[file.content_type]

    doc = Document(
        user_id=current_user.id,
        filename=file.filename,
        file_type=file_type,
        file_size=len(contents),
        storage_path=storage_path,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Process in background so we return immediately
    job = Job(
        job_type=JobType.RAG_BULK_INGEST,
        queue="rag.bulk_ingest",
        label=f"Process {file.filename}",
        payload={
            "document_id": str(doc.id),
            "user_id": str(current_user.id),
            "storage_path": storage_path,
            "file_type": file_type,
            "filename": file.filename,
        },
    )

    await publish_job(job)

    return doc


async def _process_document(
    document_id: uuid.UUID, storage_path: str, user_id: uuid.UUID
) -> None:
    
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            result_doc = await db.execute(select(Document).where(Document.id == document_id))
            doc = result_doc.scalar_one_or_none()
            if not doc:
                return
            absolute_path = str(UPLOAD_DIR.resolve() / storage_path)
            text = await extract_text(absolute_path, doc.file_type)
            await ingest_document(user_id, document_id, text, filename=doc.filename)

            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.processed = True
                await db.commit()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error(
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

    await delete_file(doc.storage_path)
    await delete_document_chunks(current_user.id, document_id)
    await db.delete(doc)
    await db.commit()
