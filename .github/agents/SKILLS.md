---
name: backend-agent-skills
description: Skills for the `hub_backend` assistant: FastAPI endpoints, SQLAlchemy models and Alembic migrations, service integrations (RabbitMQ, Redis, Ollama, ChromaDB, MinIO), and safe backend maintenance. The coordinator routes requests to single-task agents.
---

# Backend Agent — Skills Catalog

This document describes the skills, inputs/outputs, tools, safety constraints, and example prompts the `backend-agent` (see `backend-agent.agent.md`) supports for the `hub_backend` repository.

**Purpose**
- Provide a compact, discoverable list of the agent's actionable capabilities so maintainers can quickly know what to ask and what to expect.

**Quick summary**
- **Primary domain:** FastAPI backend API (REST endpoints, SQLAlchemy models, Alembic migrations, RabbitMQ, Redis, Ollama, ChromaDB, MinIO).
- **Primary outputs:** repository patches/diffs, new router files, Pydantic schemas, SQLAlchemy models, Alembic migrations, service modules, CI workflow files, and PR-ready descriptions.
- **Primary safety posture:** Prepare and validate code changes; never autonomously run database migrations or modify production data without explicit maintainer confirmation.

## Capabilities

### API Endpoints (handled by `backend-routers` agent)
- Create or update FastAPI endpoints in `app/routers/`
- Pydantic v2 request/response schemas
- Route registration in `app/main.py`
- Authentication dependencies and error handling
- httpx endpoint tests

### Database Models & Migrations (handled by `backend-database` agent)
- Create or update SQLAlchemy 2.0 async models
- Alembic migration generation and review
- Model relationships, indexes, constraints
- Matching Pydantic schemas (Create, Read, Update, List)

### Service Integrations (handled by `backend-integrations` agent)
- Service layer business logic in `app/services/`
- RabbitMQ queue publish/consume (aio-pika)
- Redis caching
- Ollama LLM integration
- ChromaDB vector search
- MinIO/S3 file storage

### Infrastructure Skills (reusable guides in `.agents/skills/`)
- `fastapi-endpoint-setup` — FastAPI endpoint creation with schemas and tests
- `sqlalchemy-model-migration` — SQLAlchemy models and Alembic migrations
- `backend-service-integration` — Service layer and external integrations
- `backend-ci-workflow` — GitHub Actions CI/CD workflow template
- `pytest-setup` — Testing patterns for FastAPI

## Inputs the agent expects (ask if missing)
- `domain` — feature domain for the endpoint (e.g., `workspaces`, `chat`)
- `model_name` — the SQLAlchemy model to create or modify
- `integration_type` — which external service to configure (RabbitMQ, Redis, Ollama, etc.)
- `migration_message` — descriptive message for the Alembic revision

## Outputs the agent produces
- New or modified router files in `app/routers/`
- SQLAlchemy models and Pydantic schemas
- Alembic migration revisions
- Service modules in `app/services/`
- CI workflow YAML files in `/.github/workflows/`
- Test files in `tests/`
- README/docs snippets describing required environment variables
- PR-ready changelog/summary and verification checklist

## Tools the agent uses
- Repository editing tools for making focused edits
- File search and read tools to inspect repo layout and find relevant files
- Progress tracking tools to manage multi-step tasks

## Safety, boundaries, and policies

- Never request or accept raw secrets in chat messages. Instead, ask for secret *names* (e.g., `DATABASE_URL`, `SECRET_KEY`) and instruct maintainers to set them in GitHub Secrets.
- Never run `alembic upgrade head` against production without the confirmation token `CONFIRM_PROD_MIGRATION`.
- No automatic PR merging or repo-level approvals — draft and explain only.

## Confirmation and escalation rules
- Low-risk edits (formatting, docs, test additions): apply patches after a single maintainer approval.
- Medium-risk edits (new endpoints, model changes that do not affect production): require explicit approval before applying.
- High-risk edits (database migrations, auth changes, production-impacting config): require `CONFIRM_PROD_MIGRATION` and a second acknowledgment.

## Example prompts (how to ask the agent)

### API Endpoints
- "Add a `GET /api/v1/workspaces` endpoint that returns all workspaces for the authenticated user."
- "Add pagination support to `GET /api/v1/notifications`."

### Database
- "Add a `workspace` table with UUID PK, name, description, owner_id FK, and timestamps."
- "Add an `avatar_url` column to the user model and generate a migration."

### Service Integrations
- "Create a notification service that publishes to the `notifications` RabbitMQ queue."
- "Add a Redis caching layer for the workspace list with a 5-minute TTL."

## Agent Architecture

The coordinator (`backend-agent`) routes to single-task agents:

| Agent | Responsibility |
|---|---|
| `backend-routers` | FastAPI endpoints and Pydantic schemas |
| `backend-database` | SQLAlchemy models and Alembic migrations |
| `backend-integrations` | Service layer and external integrations |
| `backend-planner` | Implementation planning |
| `backend-code-reviewer` | Code review before merge |

## How progress is reported
- Each agent breaks tasks into steps and reports current/completed steps

## Where to find configuration
- Agent configs: `/.github/agents/*.agent.md`
- Prompts: `/.github/prompts/*.prompt.md`
- Skills: `/.agents/skills/*/SKILL.md`
- Hooks: `/.github/hooks/*.json`
- General guidelines: `/.github/copilot-instructions.md`

## Maintenance notes
- Keep `SKILLS.md` aligned with individual agent files and prompts
- When adding a new skill, create `/.agents/skills/<name>/SKILL.md` and update this catalog
- When adding a new single-task agent, create the agent file, prompt file, register it in the coordinator's handoffs, and add to `opencode.jsonc`
