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
   ```
   *(For a zero-setup SQLite database, run `pip install aiosqlite` and use `DATABASE_URL=sqlite+aiosqlite:///./local_dev.db`)*

4. **Set up Redis:**
   Ensure Redis is running locally on the default port (6379), which is used for rate limiting and session management.
   ```bash
   # Ubuntu/Debian: sudo apt install redis && sudo systemctl start redis
   # macOS: brew install redis && brew services start redis
   # Docker: docker run -d -p 6379:6379 redis
   ```

5. **Run Database Migrations (Alembic):**
   ```bash
   alembic upgrade head
   ```

6. **Start the Development Server:**
   ```bash
   uvicorn app.main:app --reload
   ```

## Testing the API
Once the server is running, you can test the APIs interactively by navigating to:
**[http://localhost:8000/docs](http://localhost:8000/docs)**

## Running Automated Tests
To run the test suite for the authentication module and other services:
```bash
pytest
```
