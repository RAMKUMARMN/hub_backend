---
name: backend-agent-skills
description: Skills for the `hub_backend` assistant: FastAPI endpoint development, Alembic database migrations, service integration (RabbitMQ, Redis, Ollama, ChromaDB, MinIO), JWT auth, and safe backend maintenance. The agent helps maintainers set up and manage the backend API service in the repository, with a strong emphasis on safety and human oversight for production-impacting changes.
---
# Backend Agent — Skills Catalog

This document describes the skills, inputs/outputs, tools, safety constraints, and example prompts the `backend-agent` (see `backend agent.agent.md`) supports for the `hub_backend` repository.

**Purpose**
- Provide a compact, discoverable list of the agent's actionable capabilities so maintainers can quickly know what to ask and what to expect.

**Quick summary**
- **Primary domain:** FastAPI backend API (REST endpoints, database models, migrations, service integrations).
- **Primary outputs:** repository patches/diffs, GitHub Actions workflow files, CI job templates, README snippets, and PR-ready descriptions.
- **Primary safety posture:** Prepare and validate code changes; never autonomously run database migrations or modify production data without explicit maintainer confirmation.

## Capabilities

- Generate or update GitHub Actions workflows to run `ruff check`, `pytest`, and (when authorized) `alembic upgrade head`.
- Create per-environment CI workflows or a single multi-environment workflow accepting an `environment` input (`dev`, `staging`, `prod`).
- Configure Alembic migrations: generate revisions via `alembic revision --autogenerate`, review migration scripts, and apply with human gate for production.
- Produce repository patches via `apply_patch` (small, focused edits) and provide diffs for review before applying.
- Run static checks in CI: `ruff check .`, `pytest -q`, optional mypy integration.
- Draft PR descriptions, risk notes, and post-deployment verification checklists.
- Create a safe migration job template guarded by typed confirmation and restricted to manual dispatch.

## Inputs the agent expects (ask if missing)
- `environment` -- which environment to target: `dev`, `staging`, `prod`.
- `database_url` or repo secret name `DATABASE_URL` -- database connection string.
- `migration_message` -- descriptive message for the Alembic migration revision.
- `secret_names` -- repo secret names for `SECRET_KEY`, `JWT_SECRET`, `RABBITMQ_URL`, `REDIS_URL`, `AWS_ACCESS_KEY_ID`, etc.
- `notification` config -- repo secret name for `SLACK_WEBHOOK_URL` or `NOTIFICATION_EMAIL`.

## Outputs the agent produces
- New or modified workflow YAML files in `/.github/workflows/` (e.g., `backend-ci.yml`).
- New Python files (routers, models, schemas, services) or patches to existing ones.
- README/docs snippets describing required secrets and how to run the service.
- PR-ready changelog/summary and verification checklist.
- Patches (diffs) applied with `apply_patch` when given explicit permission.

## Tools the agent uses
- `apply_patch` -- create or update repo files (used only after human confirmation for impactful changes).
- `read_file`, `file_search`, `grep_search` -- inspect repo layout and find Python modules or config files.
- `manage_todo_list` -- track multi-step tasks and report progress back to the maintainer.
- `run_in_terminal` -- only if explicitly requested; otherwise the agent outputs commands for maintainers to run locally or in CI.

## Safety, boundaries, and policies

- Never request or accept raw secrets in chat messages. Instead, the agent asks for secret *names* (e.g., `DATABASE_URL`, `SECRET_KEY`) and instructs maintainers to set them in GitHub Secrets.
- Never run `alembic upgrade head` against production without an explicit confirmation token: `CONFIRM_PROD_MIGRATION` (maintainer must provide this token before the agent takes any action that would modify production database schemas).
- No direct production data access or modification outside migration workflows.
- No automatic PR merging or repo-level approvals -- the agent drafts, explains, and optionally creates patches/PRs after explicit permission.

## Confirmation and escalation rules
- Low-risk edits (formatting, docs, test additions): agent may apply patches after a single maintainer approval.
- Medium-risk edits (new endpoints, model changes that do not affect production): require an explicit approval message before applying patches.
- High-risk edits (changes that enable or run migrations in `prod`, alter database models, or modify authentication logic): require the typed confirmation `CONFIRM_PROD_MIGRATION` and a second acknowledgment (e.g., "I understand this will affect the production database").

## Example prompts (how to ask the agent)
- "Create a `backend-ci.yml` workflow that runs `ruff check` and `pytest` on push and PR; use `DATABASE_URL` repo secret; require approval for migration steps; post results to Slack via `SLACK_WEBHOOK_URL`."
- "Add a `description` column to the `workspace` table with an Alembic migration -- show me the patch before applying."
- "Draft a migration workflow that requires typed confirmation `CONFIRM_PROD_MIGRATION` and logs the operator who invoked it."

## Typical workflows the agent supports

1. Discovery: scan repo for `app/routers/*`, `app/models/*`, `app/schemas/*`, and existing migration files.
2. Draft: create a draft endpoint or migration with tests.
3. Review: produce a PR description, risk summary, and required secrets docs.
4. Apply (human-gated): upon confirmation, the agent can apply small, non-production patches or add CI steps; production migrations require `CONFIRM_PROD_MIGRATION`.

## Error handling & troubleshooting behavior
- If `ruff check` or `pytest` fails, the agent returns a concise diagnostics summary and suggests fixes.
- If `alembic upgrade head` shows conflicts or missing dependencies, the agent highlights them, explains likely causes, and recommends manual inspection steps.

## How progress is reported
- The agent uses `manage_todo_list` to break tasks into steps (discover -> draft -> patch -> verify) and will report the current step and completed steps in chat messages.

## Where to find the agent's configuration and prompts
- Agent behavior is documented in `/.github/agents/backend agent.agent.md` and the repository prompt lives at `/.github/prompts/backend-prompt.prompt.md`.

## Maintenance notes
- Keep `SKILLS.md` aligned with `backend agent.agent.md` and `backend-prompt.prompt.md` -- update all three when adding new capabilities (for example, support for a new linter or a different test framework).
