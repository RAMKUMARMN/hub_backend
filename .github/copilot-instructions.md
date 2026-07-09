---
applyTo: "**/*.py"
---

# Project coding standards for Python (FastAPI)

Apply the general coding guidelines to all code.

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
- Include `created_at` / `updated_at` timestamps on all tables (inline, no mixin)

## AI & Integration Guidelines
- LLM calls go through `app/services/llm_service.py` (proxies to AI service)
- RAG queries go through `app/services/rag_service.py` (proxies to AI service, which wraps ChromaDB)
- File storage uses `app/services/storage_service.py` (local filesystem; S3 available via `USE_S3=true`)
- Auth logic uses `app/services/auth_service.py` (JWT, bcrypt)
- Document parsing goes through `app/services/document_service.py` (proxies to AI service)

## Agent Guidelines

This repository uses the following agents:

| Agent | File | Purpose | Category |
|---|---|---|---|
| `backend-agent` | `.github/agents/backend-agent.agent.md` | Coordinator — routes to single-task agents | — |
| `backend-planner` | `.github/agents/backend-planner.agent.md` | Implementation planning | Scope/Structure |
| `backend-routers` | `.github/agents/backend-routers.agent.md` | FastAPI endpoints and Pydantic schemas | API Endpoints |
| `backend-database` | `.github/agents/backend-database.agent.md` | SQLAlchemy models, Alembic migrations, **database performance scanning** | Models/SQL |
| `backend-integrations` | `.github/agents/backend-integrations.agent.md` | Service layer (LLM/RAG/storage/auth/document proxy) | External Services |
| `backend-master-api-reviewer` | `.github/agents/backend-master-api-reviewer.agent.md` | Breaking change detection in routers/schemas against mobile + frontend contract definitions | Breaking Change Gatekeeper |

### Architectural Guardrails

- **Thin coordinator**: `backend-agent` never implements, never holds state, never waits for results. All handoffs use `send: false`.
- **DAG-only delegation**: Agent communication flows one direction. Circular calls (child → coordinator) are forbidden.
- **Max 2 concurrent agents**: No more than two specialized agents active simultaneously. Excess requests are queued.

Prompts are in `.github/prompts/` and skills in `.agents/skills/`.

When asking for help, prefix your request with the agent name:
- "@backend-routers Add a GET /api/v1/todos endpoint"
- "@backend-database Add a poll model with manual migration"
- "@backend-integrations Add a streaming chat endpoint to the LLM service"
- "@backend-master-api-reviewer Review these schema changes for breaking changes against mobile and frontend contracts"
