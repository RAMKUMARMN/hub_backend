from contextlib import asynccontextmanager
from fastapi_limiter import FastAPILimiter
from app.auth.api.oauth_routes import router as oauth_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.models import *  # noqa: F401, F403 — ensures models are registered for Alembic
from app.redis import redis_client
from app.services.vector_service import init_qdrant_collection
from app.routers import (
    admin_router,
    auth_router,
    chat_router,
    documents_router,
    poll_router,
    todos_router,
    focus_router,
)



@asynccontextmanager
async def lifespan(app: FastAPI):
    await FastAPILimiter.init(redis_client)
    await init_qdrant_collection()
    yield
    #Shutdown: close DB connections
    await redis_client.close()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="CixioHub backend API — AI-powered chat platform for TKM students",
    lifespan=lifespan,
)

# CORS — allow the Next.js frontend and Flutter web
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev (default)
        "http://localhost:3003",  # Next.js dev (CixioHub port)
        "http://localhost:8080",  # Flutter web dev
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
app.include_router(poll_router, prefix=PREFIX)
app.include_router(admin_router, prefix=PREFIX)
app.include_router(oauth_router, prefix=PREFIX)
app.include_router(focus_router, prefix=PREFIX)

@app.get("/")
async def home():
    return {"message": "CixioHub Backend Running"}

@app.get("/api/v1/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "cixiohub-backend"}


