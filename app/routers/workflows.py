from fastapi import APIRouter

from app.schemas.n8n import DocumentSummaryRequest
from app.services.n8n_service import trigger_document_summary

router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"],
)

@router.post("/document-summary")
async def document_summary(
    body: DocumentSummaryRequest,
):
    return await trigger_document_summary(
        document_text=body.document_text,
        email=body.email,
    )
