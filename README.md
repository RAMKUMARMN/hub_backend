# Backend — Hub API Server

FastAPI-based backend for Hub. Handles authentication, AI chat, document management, todo list, and admin operations.

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| **Python 3.11+** | Language |
| **FastAPI** | Web framework |
| **SQLAlchemy 2.x** | ORM |
| **Alembic** | Database migrations |
| **PostgreSQL 16** | Primary database |
| **pgvector** | Vector similarity search (RAG) |
| **Redis 7** | Session cache, rate limiting |
| **ChromaDB** | Vector store for document embeddings |
| **Ollama** | Local LLM (llama3.2:3b dev / llama3.1:70b prod) |
| **Passlib + bcrypt** | Password hashing |
| **python-jose** | JWT tokens |
| **aio-pika** | RabbitMQ async client |
| **boto3** | AWS S3 file storage |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app entry point, router registration
│   ├── config.py            # Settings loaded from environment variables
│   ├── database.py          # SQLAlchemy engine, session factory
│   ├── dependencies.py      # Shared FastAPI dependencies (get_db, get_current_user)
│   │
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── chat.py          # ChatSession, ChatMessage
│   │   ├── document.py
│   │   └── todo.py
│   │
│   ├── schemas/             # Pydantic request/response models
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── chat.py
│   │   ├── document.py
│   │   ├── todo.py
│   │   └── notify.py
│   │
│   ├── routers/             # Route handlers
│   │   ├── __init__.py
│   │   ├── auth.py          # /auth/*
│   │   ├── chat.py          # /chat/*
│   │   ├── documents.py     # /documents/*
│   │   ├── todos.py         # /todos/*
│   │   ├── admin.py         # /admin/*
│   │   └── notify.py        # /notify/* (publishes to queue)
│   │
│   ├── services/            # Business logic
│   │   ├── __init__.py
│   │   ├── auth_service.py      # JWT, password hashing, Google OAuth
│   │   ├── llm_service.py       # Ollama HTTP client, streaming
│   │   ├── rag_service.py       # ChromaDB operations, embeddings
│   │   ├── document_service.py  # File parsing (PDF, DOCX, image)
│   │   ├── storage_service.py   # S3 / local filesystem upload
│   │   └── queue_service.py     # RabbitMQ publisher
│   │
│   └── middleware/
│       └── auth.py          # JWT verification middleware
│
├── alembic/
│   ├── env.py
│   └── versions/            # Migration files (auto-generated)
│
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_chat.py
│   └── test_documents.py
│
├── alembic.ini
├── requirements.txt
├── Dockerfile
└── .env.example
```

---

## Setup & Running

### 1. Prerequisites
- Python 3.11+
- PostgreSQL running (or use Docker Compose from `infra/`)
- Redis running
- Ollama running: `ollama serve` + `ollama pull llama3.2:3b` + `ollama pull nomic-embed-text`

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your database URL, JWT secret, etc.
```

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs  
Alternative docs: http://localhost:8000/redoc

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@localhost/hub` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT signing secret (min 32 chars, random) | `openssl rand -hex 32` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access token lifetime | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `7` |
| `OLLAMA_BASE_URL` | Ollama API URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Chat model name | `llama3.2:3b` |
| `OLLAMA_EMBED_MODEL` | Embedding model | `nomic-embed-text` |
| `CHROMA_HOST` | ChromaDB host | `localhost` |
| `CHROMA_PORT` | ChromaDB port | `8002` |
| `RABBITMQ_URL` | RabbitMQ connection string | `amqp://guest:guest@localhost:5672/` |
| `AWS_ACCESS_KEY_ID` | AWS credentials | from instructor |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials | from instructor |
| `AWS_REGION` | AWS region | `ap-south-1` |
| `S3_BUCKET_NAME` | S3 bucket for file uploads | `hub-files-dev` |
| `GOOGLE_CLIENT_ID` | Google OAuth (optional) | from Google Console |
| `GOOGLE_CLIENT_SECRET` | Google OAuth (optional) | from Google Console |

---

## API Endpoints (detailed)

### Auth (`/api/v1/auth`)

#### POST `/register`
Register a new user.

Request body:
```json
{
  "email": "student@tkmce.ac.in",
  "password": "SecurePass123!",
  "full_name": "John Doe",
  "phone": "+919876543210"
}
```
Response `201`:
```json
{
  "id": "uuid",
  "email": "student@tkmce.ac.in",
  "full_name": "John Doe",
  "created_at": "2026-05-23T10:00:00Z"
}
```

#### POST `/login`
Returns access + refresh tokens.

Request body:
```json
{
  "email": "student@tkmce.ac.in",
  "password": "SecurePass123!"
}
```
Response `200`:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

#### POST `/refresh`
Exchange refresh token for a new access token.

Request body:
```json
{ "refresh_token": "eyJ..." }
```

#### GET `/me`
Returns current user profile. Requires `Authorization: Bearer <access_token>` header.

#### PUT `/profile`
Update name, phone number.

#### POST `/avatar`
Multipart file upload. Stores in S3 (or local), updates `avatar_url`.

---

### Chat (`/api/v1/chat`)

#### POST `/sessions`
Create a new chat session.

Response:
```json
{ "id": "uuid", "title": "New Chat", "created_at": "..." }
```

#### GET `/sessions`
List all sessions for current user.

#### DELETE `/sessions/{session_id}`
Delete session and all messages.

#### POST `/sessions/{session_id}/messages`
Send a message. Response is **Server-Sent Events** (SSE stream).

Request body:
```json
{
  "content": "What is machine learning?",
  "use_rag": true
}
```

SSE stream format:
```
data: {"delta": "Machine"}
data: {"delta": " learning"}
data: {"delta": " is..."}
data: [DONE]
```

#### GET `/sessions/{session_id}/messages`
Return full message history.

---

### Documents (`/api/v1/documents`)

#### POST `/upload`
Upload a file. Multipart form data, field name `file`.

Supported types: `.pdf`, `.docx`, `.txt`, `.png`, `.jpg`, `.jpeg`

Response `202` (accepted — processing happens asynchronously):
```json
{
  "id": "uuid",
  "filename": "lecture_notes.pdf",
  "file_type": "pdf",
  "file_size": 204800,
  "processed": false
}
```

#### GET `/`
List all documents for current user.

#### DELETE `/{document_id}`
Delete file from storage + remove vectors from ChromaDB.

---

### Todos (`/api/v1/todos`)

#### GET `/`
Query params: `?completed=true|false`

#### POST `/`
```json
{
  "title": "Review chapter 3",
  "description": "Focus on neural networks",
  "due_date": "2026-05-25T18:00:00Z"
}
```

#### PUT `/{todo_id}`
Update title, description, due_date.

#### PUT `/{todo_id}/complete`
Toggle completed status. Body: `{ "completed": true }`

#### DELETE `/{todo_id}`

---

### Admin (`/api/v1/admin`)

Requires `is_admin: true` on the user JWT claim.

#### POST `/users/bulk`
Upload CSV file. Columns required: `email`, `full_name`, `phone` (optional).

System creates accounts with random temp passwords and queues credential emails/SMS.

Response `202`:
```json
{ "job_id": "uuid", "total_users": 42 }
```

---

## RAG Implementation Guide

The RAG pipeline runs when a user sends a chat message with `"use_rag": true`.

### Step 1 — Document ingestion (happens on upload)

```
Upload → Extract text → Chunk (500 tokens, 50 overlap) → Embed → Store in ChromaDB
```

Text extraction libraries:
- **PDF**: `pymupdf` (`import fitz`)
- **DOCX**: `python-docx`
- **TXT**: plain read
- **Images**: `pytesseract` + `Pillow`

```python
# Example chunking
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_text(full_text)
```

### Step 2 — Retrieval (on each chat message)

```python
# Embed the user query
query_embedding = ollama.embeddings(model="nomic-embed-text", prompt=user_message)

# Query ChromaDB for top-5 similar chunks
results = collection.query(
    query_embeddings=[query_embedding["embedding"]],
    n_results=5,
    where={"user_id": current_user.id}
)
```

### Step 3 — Prompt injection

```python
context = "\n\n".join(results["documents"][0])

system_prompt = f"""You are Hub, an AI assistant for TKM students.
Use the following context to answer the question. If the context doesn't help, use your general knowledge.

Context:
{context}
"""
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use a separate `TEST_DATABASE_URL` pointed at a test database. Fixtures in `conftest.py` create and teardown tables per test session.

---

## Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---
