from fastapi import APIRouter

from app.schemas.n8n import N8NRequest
from app.services.n8n_service import trigger_n8n


router = APIRouter(
    prefix="/n8n-test",
    tags=["n8n"],
)


@router.post("/")
async def trigger_n8n(body: N8NRequest):

    result = await trigger_n8n(
        task=body.task,
        message=body.message,
    )

    return result
