---
name: backend-service-integration
description: Set up service layer business logic in app/services/ following the project's patterns: stateless functions, proxy through AI service for LLM/RAG/document extraction, local file storage, and JWT auth.
metadata:
  model: models/gemini-3.1-pro-preview
  last_modified: Mon, 29 Jun 2026 00:00:00 GMT
---

# Backend Service Integration

## Contents
- [Service Pattern](#service-pattern)
- [Auth Service (JWT + bcrypt)](#auth-service-jwt--bcrypt)
- [LLM Service (AI service proxy)](#llm-service-ai-service-proxy)
- [RAG Service (AI service proxy)](#rag-service-ai-service-proxy)
- [Document Service (AI service proxy)](#document-service-ai-service-proxy)
- [Storage Service (local filesystem)](#storage-service-local-filesystem)
- [AI Service Architecture](#ai-service-architecture)
- [Verification](#verification)

## Service Pattern

Services are stateless functions in `app/services/`. No classes, no shared mutable state:

```python
# app/services/auth_service.py — simple self-contained service
from jose import jwt
import bcrypt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode.update({"exp": ..., "type": "access"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
```

## Auth Service (JWT + bcrypt)

**File:** `app/services/auth_service.py`

| Function | Purpose |
|---|---|
| `hash_password(password)` | bcrypt hash with salt |
| `verify_password(plain, hashed)` | bcrypt verify |
| `create_access_token(data)` | JWT with short exp, type=access |
| `create_refresh_token(data)` | JWT with longer exp, type=refresh |
| `decode_token(token)` | Decode + validate JWT, raises `JWTError` |

## LLM Service (AI service proxy)

**File:** `app/services/llm_service.py`

Proxies chat streaming and embedding to the external AI service at `settings.ai_service_url`:

```python
async def chat_stream(
    messages: list[dict],
    user_id: str,
    context_chunks: list[str] | None = None,
    use_rag: bool = False,
) -> AsyncIterator[str]:
    """Stream tokens from the AI service chat endpoint (SSE)."""
    async with httpx.AsyncClient(base_url=settings.ai_service_url, timeout=120) as client:
        async with client.stream("POST", "/api/v1/chat/stream", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data == "[DONE]":
                        return
                    yield json.loads(data).get("delta", "")


async def get_embedding(text: str) -> list[float]:
    """Get a text embedding vector from the AI service."""
```

## RAG Service (AI service proxy)

**File:** `app/services/rag_service.py`

Proxies vector storage/retrieval to the AI service (which wraps ChromaDB):

```python
async def ingest_document(user_id, document_id, text, filename) -> int:
    """Send extracted text for chunking, embedding, and ChromaDB storage."""


async def retrieve_chunks(user_id, query, n_results=5) -> list[str]:
    """Ask for top-k relevant chunks."""


async def delete_document_chunks(user_id, document_id) -> None:
    """Remove all chunks for a document."""
```

## Document Service (AI service proxy)

**File:** `app/services/document_service.py`

Proxies text extraction to the AI service (which handles PDF via PyMuPDF, DOCX via python-docx, OCR via Tesseract):

```python
async def extract_text(file_path: str, file_type: str) -> str:
    """Extract plain text from a file via the AI service."""
    async with httpx.AsyncClient(base_url=settings.ai_service_url, timeout=120) as client:
        response = await client.post(
            "/api/v1/extract",
            json={"file_path": file_path, "file_type": file_type},
        )
        response.raise_for_status()
        return response.json()["text"]
```

## Storage Service (local filesystem)

**File:** `app/services/storage_service.py`

Local filesystem storage in `uploads/` directory. S3 support is planned but not yet implemented.

```python
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


async def save_file(file_bytes: bytes, filename: str, user_id: uuid.UUID) -> str:
    """Save to local `uploads/{user_id}/{uuid}_{filename}`. Returns relative path."""
    unique_name = f"{uuid.uuid4()}_{filename}"
    user_dir = UPLOAD_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / unique_name
    dest.write_bytes(file_bytes)
    return str(dest.relative_to(UPLOAD_DIR.resolve()))


async def delete_file(storage_path: str) -> None:
    """Delete from local filesystem."""
    path = Path(storage_path)
    if path.exists():
        path.unlink()
```

## AI Service Architecture

Several backend services proxy to a separate **AI service** (`cixio-hub/ai`, running on port 8003). This is intentional:

| Backend service | Proxies to AI service endpoint | AI service handles |
|---|---|---|
| `llm_service.py` | `/api/v1/chat/stream`, `/api/v1/embed` | Ollama streaming, embeddings |
| `rag_service.py` | `/api/v1/rag/ingest`, `/api/v1/rag/retrieve`, `/api/v1/rag/documents/{id}` | ChromaDB chunking, embedding, search |
| `document_service.py` | `/api/v1/extract` | PyMuPDF (PDF), python-docx (DOCX), Tesseract (OCR) |

Config values for direct Ollama/ChromaDB connections exist in `app/config.py` but are not used by the backend — they're reserved for the AI service.

## Verification

1. `python -c "from app.services.auth_service import hash_password, verify_password"` — auth imports
2. `python -c "from app.services.llm_service import chat_stream"` — llm imports
3. Start the server and test endpoints that use these services
4. External connections are mocked in unit tests
