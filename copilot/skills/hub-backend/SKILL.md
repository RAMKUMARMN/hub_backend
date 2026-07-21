---
title: Hub Backend Skill
applyTo: "**/*.py"
---

# Hub Backend (FastAPI) Skill

Purpose: provide repository-specific guidance and quick prompts to help Copilot-style assistants write, review, and refactor code for this FastAPI backend.

Key points
- Framework: FastAPI (async first)
- Validation: Pydantic v2 for schemas
- DB: SQLAlchemy 2.0 async style, Alembic for migrations
- Auth: JWT flows in app/services/auth_service.py
- Routes: grouped under app/routers/ and prefixed with /api/v1/

Coding conventions (repo-specific)
- Prefer `async def` for I/O-bound handlers and services.
- Keep route handlers thin; delegate business logic to `app/services/`.
- Type-annotate all function signatures and Pydantic models.
- Use UUID primary keys, and include `created_at` / `updated_at` timestamps on models.
- Use dependency-injection for shared objects (db, current_user).

Common tasks & commands
- Install dependencies: `pip install -r requirements.txt`
- Run tests: `pytest -q`
- Run migrations: `alembic upgrade head`

Suggested assistant prompts
- Create a new router for X resource: define SQLAlchemy model, Pydantic schemas, service, router tests, and Alembic migration.
- Refactor this route to move business logic to a service and add unit tests for the service.
- Write Pydantic v2 schema for this model and include validators for X and Y.

PR checklist (enforced by skill)
- Add/modify Alembic migration for schema changes
- Add unit tests for business logic in `app/services/`
- Keep handlers minimal and covered by integration tests where appropriate

Sources: tuned to this repository structure and common FastAPI patterns.
