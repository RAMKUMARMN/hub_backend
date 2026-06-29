---
applyTo: "**/*.py"
---

# Project coding standards for Python (FastAPI)

Apply the [general coding guidelines](./general-coding.instructions.md) to all code.

## Python Guidelines
- Use Python 3.10+ features: type hints, match statements, union syntax (`X | Y`)
- Use async/await for all I/O-bound operations
- Use Pydantic v2 for all request/response validation
- Use SQLAlchemy 2.0 async session style (`select()` / `await db.execute()`)
- Prefer composition over inheritance for service classes
- Use explicit error handling with custom HTTPException subclasses
- Type annotate all function signatures and class attributes

## FastAPI Guidelines
- Group endpoints in `app/routers/` by domain (auth, chat, todos, etc.)
- Use dependency injection for shared concerns (DB session, current user)
- Prefix all routes with `/api/v1/`
- Use Pydantic schemas for request bodies and response models
- Keep route handlers thin — delegate business logic to `app/services/`

## Database Guidelines
- All schema changes via Alembic migrations — no raw SQL
- Models in `app/models/`, schemas in `app/schemas/`
- Use UUIDs for primary keys
- Include `created_at` / `updated_at` timestamps on all tables
- Use soft deletes where applicable

## AI & Integration Guidelines
- LLM calls go through `app/services/llm_service.py`
- RAG queries use ChromaDB via `app/services/rag_service.py`
- File storage uses S3-compatible API via `app/services/storage_service.py`
- Queue messages published to RabbitMQ via aio-pika

## Agent Guidelines

This repository uses the following agents:

| Agent | File | Purpose |
|---|---|---|
| `backend-agent` | `.github/agents/backend-agent.agent.md` | Coordinator — routes to single-task agents |
| `backend-routers` | `.github/agents/backend-routers.agent.md` | FastAPI endpoints and Pydantic schemas |
| `backend-database` | `.github/agents/backend-database.agent.md` | SQLAlchemy models and Alembic migrations |
| `backend-integrations` | `.github/agents/backend-integrations.agent.md` | Service layer and external integrations |
| `backend-planner` | `.github/agents/backend-planner.agent.md` | Implementation planning |
| `backend-code-reviewer` | `.github/agents/backend-code-reviewer.agent.md` | Code review before merge |

Prompts are in `.github/prompts/` and skills in `.agents/skills/`.

When asking for help, prefix your request with the agent name:
- "@backend-routers Add a GET /api/v1/workspaces endpoint"
- "@backend-database Add a workspace table with migration"
- "@backend-integrations Set up RabbitMQ notification consumer"
