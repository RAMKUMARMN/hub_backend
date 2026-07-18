import httpx

from app.config import settings


async def trigger_n8n(message: str, task: str):
    payload = {
        "message": message,
        "task": task,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            settings.n8n_webhook_url,
            json=payload,
        )

    response.raise_for_status()

    return response.json()


async def trigger_document_summary(
    document_text: str,
    email: str,
):
    payload = {
        "document_text": document_text,
        "email": email,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            settings.n8n_webhook_url,
            json=payload,
        )

    response.raise_for_status()

    return response.json()
