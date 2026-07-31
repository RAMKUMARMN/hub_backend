# CixioHub Backend API

This is the FastAPI backend for CixioHub, an AI-powered chat platform for TKM students.

---

## 🚀 Choose Your Setup Method

You can run CixioHub in **two ways**:
- **[Option A: Full Docker Compose Setup](#option-a-full-docker-compose-setup)** (Runs backend, databases, Redis, and Qdrant via Docker)
- **[Option B: Native Localhost Setup](#option-b-native-localhost-setup-without-docker)** (Runs backend & AI service natively via Python `uvicorn`)

---

## Prerequisites (Both Options)

1. **Ollama** installed on your host machine ([ollama.com](https://ollama.com)):
   ```bash
   ollama serve
   ```
2. **Pull Required Ollama Models:**
   ```bash
   ollama pull nomic-embed-text
   ollama pull qwen3.5:4b
   ollama pull qwen3-vl:2b
   ```

---

## Option A: Full Docker Compose Setup

Run backend and supporting databases inside Docker containers.

### 1. Configure Environment File
```bash
cd hub_backend
cp .env.example .env
```
Ensure your `.env` contains:
```env
DATABASE_URL=postgresql+asyncpg://cixiohub:cixiohub@db:5432/cixiohub
REDIS_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333
OLLAMA_BASE_URL=http://host.docker.internal:11434
AI_SERVICE_URL=http://host.docker.internal:8003
USE_REMOTE_AI=True
AI_API_KEY=1234
ENABLE_VISION_RAG=True
```

### 2. Start Services via Docker Compose
```bash
docker compose up -d --build
```
This spins up:
- `cixiohub_backend` (FastAPI on port `8000`)
- `cixiohub_db` (PostgreSQL on port `5433`)
- `cixiohub_redis` (Redis on port `6379`)
- `cixiohub_qdrant` (Qdrant Vector DB on port `6333`)

### 3. View Logs
```bash
docker compose logs -f web
```

---

## Option B: Native Localhost Setup (Without Docker)

Run the FastAPI backend natively using Python `uvicorn`.

### 1. Start Supporting Databases in Docker
You only need PostgreSQL, Redis, and Qdrant running:
```bash
cd hub_backend
docker compose up -d db redis qdrant
```

### 2. Create Python Virtual Environment & Install Dependencies
```bash
cd hub_backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure `.env` for Localhost
```env
DATABASE_URL=postgresql+asyncpg://cixiohub:cixiohub@localhost:5433/cixiohub
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
OLLAMA_BASE_URL=http://localhost:11434
AI_SERVICE_URL=http://localhost:8003
USE_REMOTE_AI=True
AI_API_KEY=1234
ENABLE_VISION_RAG=True
```

### 4. Run Database Migrations (Alembic)
```bash
alembic upgrade head
```

### 5. Start Backend Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🔗 API Documentation
Once running (Docker or Localhost), visit:
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

## 🧪 Running Tests
```bash
# Run unit tests
pytest -m "not live"

# Run integration tests (with active services)
pytest -m "live"
```
