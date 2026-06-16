---
mode: agent
agent: backend-agent
name: backend-agent-prompt
description:
  A system prompt for the `hub_backend` assistant. It defines the agent's role as a focused backend API helper for the repository, outlines allowed tools, behavior rules, response format, safety heuristics, and developer hints to ensure safe and effective assistance with FastAPI development, database operations, and service integration tasks.
---

### Requirements:

1.  **API Development and Testing:**
    *   The workflow should support running the FastAPI dev server via `uvicorn` for local development.
    *   It must include steps to run linting (`ruff`) and tests (`pytest -q`) before merging.
    *   API endpoints should follow RESTful conventions with proper request/response schemas using Pydantic.
    *   Support for environment-specific configurations via Pydantic settings (e.g., `dev`, `staging`, `prod`).
    *   Secrets (e.g., `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET`) must be managed through environment variables and never hardcoded.

2.  **Database Migrations:**
    *   Include steps to generate and apply Alembic migrations safely.
    *   Migration operations should be reviewed before applying to production databases.
    *   Support for dry-run migrations (`alembic current`) to verify state before applying changes.
    *   Migration rollback strategy should be documented and tested.

3.  **Service Integration and Messaging:**
    *   Provide guidance for configuring and testing integrations with PostgreSQL, Redis, RabbitMQ, Ollama, ChromaDB, and MinIO/S3.
    *   RabbitMQ queue producers and consumers should be testable with local dry-runs.
    *   LLM and RAG pipelines should be verifiable with sample queries without affecting production state.
    *   JWT authentication flows should be testable with development tokens.

4.  **CI/CD and Containerization:**
    *   GitHub Actions CI should run lint, test, and optionally migration checks on push and PR.
    *   Docker images should follow multi-stage builds for optimized size.
    *   Support for Docker Compose for local development with all dependent services (DB, Redis, RabbitMQ, MinIO, Ollama).

### Constraints:

*   **Language:** Python 3.10+.
*   **Framework:** FastAPI with async support.
*   **Database:** PostgreSQL with SQLAlchemy (async) and Alembic for migrations.
*   **Message Queue:** RabbitMQ via aio-pika.
*   **AI/LLM:** Ollama (llama3.2:3b) with ChromaDB for vector storage.
*   **Object Storage:** S3-compatible (MinIO) via boto3.
*   **Caching:** Redis.
*   **CI/CD Platform:** GitHub Actions.
*   **Security:** Adhere to the principle of least privilege. Do not hardcode sensitive information.
*   **Idempotency:** All database migrations and API operations must be idempotent where applicable.

### Success Criteria:

*   The dev server starts successfully with `uvicorn app.main:app --reload`.
*   All linting checks pass (`ruff check .`) and all tests pass (`pytest -q`) without errors.
*   Alembic migrations apply cleanly in both directions (upgrade and downgrade).
*   API endpoints return correct responses with appropriate HTTP status codes and error handling.
*   RabbitMQ queues process messages without unexpected failures.
*   Docker Compose environment starts all services and the backend connects successfully.
*   CI pipeline runs successfully on push and pull request events.

### Usage Template (copy-paste)

Below are ready-to-use prompt templates you can paste to the `backend-agent` chat to generate workflows, patches, and documentation. Replace bracketed values before sending.

- CI workflow setup:

```
Generate a GitHub Actions workflow `/.github/workflows/backend-ci.yml` with these behaviours:
- Triggers: `push` to `main`, `pull_request`, `workflow_dispatch`.
- Jobs: `lint` (ruff check), `test` (pytest -q with matrix on Python 3.10, 3.11), `migrations` (manual trigger with alembic current dry-run).
- Caching: pip dependencies cache.
- Services: PostgreSQL service container for tests.
- Notifications: post summary to Slack via `SLACK_WEBHOOK_URL`.

Inputs to set: `DATABASE_URL`, `SECRET_KEY`, `REDIS_URL`, `RABBITMQ_URL`, `SLACK_WEBHOOK_URL` (all stored as GitHub Secrets).

Deliverables: workflow file, README snippet for secrets and usage, PR body template, and a verification checklist. Provide diffs and wait for approval before applying changes. Require `CONFIRM_PROD_MIGRATION` for any migration affecting production.
```

- Database migration plan:

```
I need to add a new `workspace` table to the database with columns: `id` (UUID, PK), `name` (VARCHAR 255), `owner_id` (FK to users), `created_at`, `updated_at`. Generate an Alembic migration for this change.
Steps:
1. Show the proposed SQLAlchemy model for the `workspace` table.
2. Generate the Alembic migration revision using `alembic revision --autogenerate`.
3. Review the generated migration script and verify it's correct.
4. Ask for confirmation before applying with `alembic upgrade head`.

Do NOT apply the migration without explicit confirmation.
```

- Add a new API endpoint:

```
Add a new REST endpoint `GET /api/v1/workspaces` that returns all workspaces for the authenticated user.
Follow the existing patterns:
- Create a new router file at `app/routers/workspaces.py`.
- Add a Pydantic schema in `app/schemas/` for the response.
- Add a service function in `app/services/`.
- Register the router in `app/main.py`.
- Include authentication via the existing JWT dependency.
- Write a test in `tests/test_workspaces.py`.

Show diffs and wait for my confirmation before applying patches.
```

### Chat example (copy-paste)

Use these short chat transcripts to interact with the `backend-agent`. Paste, edit the bracketed values, and send.

- Minimal CI setup flow:

```
User: Create a CI workflow for hub_backend that runs ruff linting and pytest on push and PR. Python matrix 3.10 and 3.11. Use a PostgreSQL service container for tests. Show diffs and wait for my confirmation before applying.
```

Agent (expected):
- Scans repository for existing workflow and config files.
- Produces draft `backend-ci.yml` and shows a unified diff.
- Asks: "Do you want me to apply these changes to the repo? (yes/no)"

User:
```
yes
```

- Migration with production guard:

```
User: Generate a migration to add a `workspace` table. Show the diff and do NOT apply to production without a confirmation token.
```

Agent (expected):
- Reviews existing models and generates migration script.
- Shows the diff and asks for explicit confirmation with the token.

User (to approve production migration):
```
I confirm the proposed migration and authorize applying it.
Confirmation token: CONFIRM_PROD_MIGRATION
I understand this may affect the production database schema.
```

Agent (after confirmation):
- Applies the migration, commits or opens a PR.
- Posts a verification checklist and rollback command.

If the agent needs missing inputs (e.g., database URL secret name), it will ask a single targeted question such as: "Please confirm the GitHub secret name for `DATABASE_URL`."
