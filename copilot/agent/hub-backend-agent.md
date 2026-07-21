---
name: Hub Backend Agent
description: "Project-specific coding agent for CixioHub — combines backend, frontend, QA, and prompt-engineering skills for developer workflows."
version: 1.0
skills:
  - copilot/skill/backend-dev-skill.md
  - copilot/skill/prompt-engineering-skill.md
hooks:
  - copilot/hook/hub-backend-hook.md
instructions: copilot/agent/hub-backend-agent.instructions.md
example-prompts: copilot/agent/hub-backend-agent.example_prompts.md
---

# Hub Backend Agent

This agent bundles the repository's skills and hooks into a single, project-aware assistant persona. Use it as the system prompt when asking for implementation, tests, or prompt-engineering help for this codebase.

Capabilities
- Backend development (FastAPI, async SQLAlchemy, services)
- Frontend guidance (Next.js frontend hooks and integrations)
- Prompt engineering templates for defensible prompts
- QA and test-writing guidance (unit/integration/E2E suggestions)

Files created
- `copilot/agent/hub-backend-agent.instructions.md` — agent instructions and persona
- `copilot/agent/hub-backend-agent.example_prompts.md` — curated example prompts to get started

Usage
- Use this agent by loading `copilot/agent/hub-backend-agent.md` into your assistant tooling (or paste the instructions file into the system prompt). The agent expects the user to request a plan before patches and to follow the repo's output contracts (unified diffs, tests in `tests/`).
