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
   * **Linux/macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   * **Windows (Command Prompt):**
     ```cmd
     python -m venv venv
     venv\Scripts\activate.bat
     ```
   * **Windows (PowerShell):**
     ```powershell
     python -m venv venv
     Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
     .\venv\Scripts\Activate.ps1
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
   
   # Vision RAG configurations
   ENABLE_VISION_RAG=True
   OLLAMA_VISION_MODEL=qwen3-vl:2b
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

   # Pull the vision model (used for page re-inspection fallback)
   ollama pull qwen3-vl:2b
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

## Setup using Docker (FastAPI Web App Only)

If you want to run only the FastAPI application inside a Docker container while your other services (PostgreSQL, Redis, Qdrant, RabbitMQ, Mailpit, and Ollama) run natively on your host machine:

### 1. Ensure Host Services are Running

Make sure your databases and helper services are active on your local device. If you run them via Docker containers locally:
*   **Mailpit (SMTP):** `docker start hub-mailpit` (or run it fresh: `docker run -d --name hub-mailpit -p 1025:1025 -p 8025:8025 axllent/mailpit`)
*   **Qdrant (Vector DB):** `docker start local-qdrant` (or run it fresh: `docker run -d --name local-qdrant -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage qdrant/qdrant:latest`)
*   **PostgreSQL:** `sudo systemctl start postgresql` (or make sure your native service is active)
*   **Redis:** `sudo systemctl start redis` (or make sure your native service is active)
*   **Ollama:** `ollama serve` (ensure the server daemon is active)

---

### 2. Linux Setup (Default)

Since you are running Linux, the default configuration uses **Host Networking** (`network_mode: "host"`). This connects the container directly to your host's loopback interface (`localhost`) without extra port mappings.

1. **Copy the Docker environment template:**
   * **Linux/macOS/Git Bash:**
     ```bash
     cp .env.docker .env
     ```
   * **Windows (CMD):**
     ```cmd
     copy .env.docker .env
     ```
2. **Start the backend container:**
   ```bash
   docker compose up --build
   ```

---

### 3. Windows & macOS Setup

Because Windows and macOS run Docker inside a lightweight virtual machine, they do not support Linux's native `network_mode: "host"`. You need to adjust two settings to connect the container to your host machine:

#### A. Configure Docker Desktop (Windows Only)
- Ensure **Docker Desktop** is running.
- Open **Settings > General** and check **"Use the WSL 2 based engine"** (enables WSL 2 integration).
- Open **Settings > Resources > WSL integration** and turn on integration for your active WSL Linux distro.

#### B. Modify `docker-compose.yml`
Open [docker-compose.yml](file:///home/albin/Cixio/hub_backend/docker-compose.yml) and change it to bridge mode:
```yaml
services:
  web:
    build:
      context: .
      dockerfile: Dockerfile
    # 1. Comment out or remove network_mode:
    # network_mode: "host"
    
    # 2. Explicitly map ports:
    ports:
      - "8000:8000"
    
    volumes:
      - .:/app
      - uploads:/app/uploads
    env_file:
      - .env
    
    # 3. Add extra hosts mapping:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

#### C. Modify your `.env` file
Change all occurrences of `localhost` in your `.env` file to **`host.docker.internal`** so the container can resolve your computer's IP address:
```env
DATABASE_URL=postgresql+asyncpg://cixiohub:cixiohub@host.docker.internal:5432/cixiohub
REDIS_URL=redis://host.docker.internal:6379/0
QDRANT_URL=http://host.docker.internal:6333
RABBITMQ_URL=amqp://guest:guest@host.docker.internal:5672/
SMTP_HOST=host.docker.internal
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

#### D. Start the backend container
```bash
docker compose up --build
```

---

### 4. Accessing the APIs (All OS)
*   **FastAPI Web App & Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

## Testing the API
Once the server is running (either locally or via Docker), you can test the APIs interactively by navigating to:
**[http://localhost:8000/docs](http://localhost:8000/docs)**

## Running Automated Tests

Tests are categorized into **live integration tests** (which require running local databases, Qdrant, and Ollama) and **in-memory mocked unit tests**.

### Running Tests Locally:
* **Run ONLY Mocked Unit/CI Tests (Default, runs instantly without local services):**
  ```bash
  pytest -m "not live"
  ```
* **Run ONLY Live Integration Tests (requires running local services):**
  ```bash
  pytest -m "live"
  ```
* **Run all tests:**
  ```bash
  pytest
  ```

### Running Tests inside Docker:
* **Run only unit tests inside Docker container:**
  ```bash
  docker compose exec web pytest -m "not live"
  ```
* **Run only live integration tests inside Docker container:**
  ```bash
  docker compose exec web pytest -m "live"
  ```
