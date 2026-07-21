# Backend Agent Architecture

This document describes the custom agents and reusable skills available for the `hub_backend` repository. Use it to understand which agent to route a task to and which skill to load for conventions.

## Agent Catalog

| Agent | Purpose | Skill | When to route |
|---|---|---|---|
| `backend-routers` | FastAPI REST endpoints, Pydantic schemas, route registration, endpoint tests | `fastapi-endpoint-setup`, `pytest-setup` | Creating or updating API endpoints |
| `backend-database` | SQLAlchemy 2.0 async models, Alembic migrations, DB performance scans | `sqlalchemy-model-migration`, `pytest-setup` | Model changes, migrations, N+1 detection |
| `backend-integrations` | Service layer business logic, AI service proxy (LLM/RAG/document), local file storage, JWT auth | `backend-service-integration`, `pytest-setup` | External service integration |
| `backend-planner` | Implementation planning, file structure, dependency order, risk assessment | *(all skills for awareness)* | Ambiguous or multi-step tasks needing a plan first |
| `backend-master-api-reviewer` | Breaking change detection against hub_mobile (Dart) and hub_frontend (TypeScript) contracts | `fastapi-endpoint-setup` | Schema or router changes that may break clients |
| `backend-agent` | Thin coordinator — routes to exactly one specialist, never implements | *(none)* | Entry point for any task |

## Agent Details

### backend-routers

- **Scope:** `app/routers/<domain>.py`, `app/schemas/`, `app/dependencies.py`, `app/main.py`, `tests/test_<domain>.py`
- **Out of scope:** Models/migrations (`backend-database`), service logic (`backend-integrations`)
- **Load skill:** `fastapi-endpoint-setup` for FastAPI conventions (prefix `/api/v1/`, dependency injection, Pydantic v2)
- **Load skill:** `pytest-setup` for endpoint test patterns (httpx.AsyncClient, async DB fixtures)

### backend-database

- **Scope:** `app/models/`, `app/schemas/`, `alembic/versions/`, `app/database.py`; also N+1 detection, index analysis, migration impact
- **Out of scope:** Endpoint handlers (`backend-routers`), service integrations (`backend-integrations`)
- **Load skill:** `sqlalchemy-model-migration` for conventions (UUID PKs, timestamps, async sessions)
- **Load skill:** `pytest-setup` for model/service test patterns

### backend-integrations

- **Scope:** `app/services/` (auth, LLM, RAG, storage, document)
- **Out of scope:** Endpoints (`backend-routers`), models (`backend-database`)
- **Load skill:** `backend-service-integration` for service patterns (stateless functions, error handling, retry logic)
- **Load skill:** `pytest-setup` for integration test patterns

### backend-planner

- **Scope:** Generate step-by-step plans for new endpoints, DB changes, service integrations, or refactoring
- **Out of scope:** Implementing code — hands off to domain agents
- **Instructions:** Cover file order, dependencies, risks, rollback, and validation commands

### backend-master-api-reviewer

- **Scope:** Breaking change detection against `hub_mobile/lib/models/*.dart` and `hub_frontend/src/types/index.ts` (plus inline interfaces in pages)
- **Detection:** Field removal, rename, type change, optionality shift, path param changes, status code changes
- **Output:** Structured report with `CRITICAL: BREAKING CHANGE` flags and client-side update snippets

### backend-agent (coordinator)

- **Strictly thin:** Never implements, never holds state, never waits for results
- **Handoffs:** All `send: false` (fire-and-forget) to `backend-planner`, `backend-routers`, `backend-database`, `backend-integrations`, `backend-master-api-reviewer`
- **Route to exactly ONE specialist per request.** If ambiguous, ask the user to clarify.

## Skill Reference

Skills in `.agents/skills/<name>/SKILL.md` are reusable guides loaded when relevant:

| Skill | Agents | What it provides |
|---|---|---|
| `fastapi-endpoint-setup` | `backend-routers`, `backend-master-api-reviewer` | Router structure, endpoint template, Pydantic schemas, deps, error handling |
| `sqlalchemy-model-migration` | `backend-database` | Model template, relationships, inline timestamps, Alembic migration, Pydantic schemas |
| `backend-service-integration` | `backend-integrations` | Service pattern, AI service proxy for LLM/RAG/document extraction, local file storage, JWT auth |
| `pytest-setup` | `backend-routers`, `backend-database`, `backend-integrations` | Test structure, fixtures (DB, async client, auth), endpoint and service test patterns |
| `backend-ci-workflow` | *(infra-level, no specific agent)* | GitHub Actions CI with ruff, pytest, PostgreSQL service container, type checking |

## Routing Rules (DAG)

- **Thin coordinator:** `backend-agent` routes to exactly one specialist per request; never implements.
- **One-way delegation:** All agent-to-agent calls flow in a DAG. Child agents never call back to the coordinator.
- **Max 2 concurrent agents:** No more than two specialized agents active simultaneously. Queue excess requests.

## Safety Policies

- Never request or expose raw secrets. Ask for secret *names* (e.g., `DATABASE_URL`) and instruct maintainers to set them in environment or GitHub Secrets.
- Never run `alembic upgrade head` against production without confirmation token `CONFIRM_PROD_MIGRATION`.
- Low-risk edits (formatting, docs, tests): apply after single approval.
- Medium-risk edits (new endpoints, model changes): require explicit approval.
- High-risk edits (DB migrations, auth changes, production config): require `CONFIRM_PROD_MIGRATION` + second acknowledgment.
