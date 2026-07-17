from contextlib import asynccontextmanager
from fastapi_limiter import FastAPILimiter
from app.auth.api.oauth_routes import router as oauth_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import Base, engine
from app.models import *  # noqa: F401, F403 — ensures models are registered for Alembic
from app.redis import redis_client

from app.routers import (
    admin_router,
    auth_router,
    chat_router,
    devices_router,
    documents_router,
    todos_router,
    focus_router,
    calendar_router,
    preferences_router,
    system_router,
    roles_router,
    notes_router,
    folders_router,
    dashboard_router,
    n8n_test_router,
    workflows_router,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create database tables on startup (perfect for zero-setup SQLite)
    try:
        from app.database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Database tables initialized successfully.")
    except Exception as e:
        print("Error initializing database tables:", e)

    try:
        await FastAPILimiter.init(redis_client)
    except Exception as e:
        print("Redis not available:", e)
    yield

    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="CixioHub backend API — AI-powered chat platform for TKM students",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
)

# CORS — allow the Next.js frontend and Flutter web
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
        "http://127.0.0.1:3003",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers under /api/v1
PREFIX = "/api/v1"
app.include_router(auth_router, prefix=PREFIX)
app.include_router(chat_router, prefix=PREFIX)
app.include_router(documents_router, prefix=PREFIX)
app.include_router(todos_router, prefix=PREFIX)
app.include_router(admin_router, prefix=PREFIX)
app.include_router(oauth_router, prefix=PREFIX)
app.include_router(focus_router, prefix=PREFIX)
app.include_router(calendar_router, prefix=PREFIX)
app.include_router(notes_router, prefix=PREFIX)
app.include_router(folders_router, prefix=PREFIX)
app.include_router(dashboard_router, prefix=PREFIX)
app.include_router(devices_router, prefix=PREFIX)
app.include_router(n8n_test_router, prefix=PREFIX)
app.include_router(workflows_router, prefix=PREFIX)

app.include_router(preferences_router, prefix=PREFIX)
app.include_router(system_router, prefix=PREFIX)
app.include_router(roles_router, prefix=PREFIX)

@app.get("/")
async def home():
    return {"message": "CixioHub Backend Running"}

@app.get("/api/v1/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "cixiohub-backend"}

