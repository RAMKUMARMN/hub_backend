# CixioHub Backend API

This is the FastAPI backend for CixioHub, an AI-powered chat platform for TKM students.

## Features
- **FastAPI** for high-performance, async API endpoints
- **SQLAlchemy 2.0** for async database ORM
- **Alembic** for database migrations
- **Domain-Driven Design** (Vertical Slicing) for modularity (e.g., dedicated `app/auth/` module)

## Prerequisites
- Python 3.10+
- PostgreSQL (or SQLite for local dev)
- Redis (Required for rate limiting and session management)
- Qdrant (Required for vector storage and RAG document search)
- Ollama (Required for LLM chat and embeddings generation)

## Setup Instructions

1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file in the root directory (alongside `main.py`). If using Postgres, configure it like so:
   ```env
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/cixiohub
   REDIS_URL=redis://localhost:6379/0
   
   # Ollama configurations
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=qwen3.5:4b
   OLLAMA_EMBED_MODEL=nomic-embed-text
   
   # Qdrant configurations
   QDRANT_URL=http://localhost:6333
   QDRANT_COLLECTION=user_documents
   ```
   *(For a zero-setup SQLite database, run `pip install aiosqlite` and use `DATABASE_URL=sqlite+aiosqlite:///./local_dev.db`)*

4. **Set up Redis:**
   Ensure Redis is running locally on the default port (6379), which is used for rate limiting and session management.
   ```bash
   # Ubuntu/Debian: sudo apt install redis && sudo systemctl start redis
   # macOS: brew install redis && brew services start redis
   # Docker: docker run -d -p 6379:6379 redis
   ```

5. **Set up Qdrant Vector DB:**
   Start the Qdrant container locally to index and search vector embeddings:
   ```bash
   docker run -d -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage qdrant/qdrant
   ```

6. **Set up Ollama & pull embedding/LLM models:**
   Ensure Ollama is running and download the embedding model and LLM:
   ```bash
   # Pull the embedding model (used for vector storage)
   ollama pull nomic-embed-text

   # Pull the chat model (e.g. qwen3.5:4b, llama3.2:3b, or deepseek-r1)
   ollama pull qwen3.5:4b
   ```

7. **Set up Local Email Catcher (SMTP):**
   Ensure an SMTP mail catcher is running on port `1025` to receive OTP codes and password reset links.
   * **Using Node (Easiest, zero-setup)**:
     ```bash
     npx maildev --smtp 1025 --web 8025
     ```
   * **Using Docker**:
     ```bash
     docker run -d --name hub-mailpit -p 1025:1025 -p 8025:8025 axllent/mailpit
     ```
   You can view caught emails in your web browser at `http://localhost:8025`.
   *(If no mail catcher is running, emails will fall back to printing directly inside the backend server console).*

8. **Run Database Migrations (Alembic):**
   ```bash
   alembic upgrade head
   ```

9. **Start the Development Server:**
   ```bash
   uvicorn app.main:app --reload
   ```

## Testing the API
Once the server is running, you can test the APIs interactively by navigating to:
**[http://localhost:8000/docs](http://localhost:8000/docs)**

## Running Automated Tests
To run all tests (including authentication and local AI/RAG integration tests):
```bash
pytest
```

To run only the new AI and RAG integration tests:
```bash
pytest tests/test_chat_rag.py -s -v
```

To run only the authentication and OTP module tests:
```bash
pytest app/auth/tests -v
```
