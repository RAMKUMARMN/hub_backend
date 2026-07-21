---
mode: agent
agent: backend-agent
name: backend-agent-prompt
description: "Coordinator prompt for the hub_backend repository. Routes requests to the appropriate single-task agent based on the task domain."
---

This coordinator does NOT implement tasks directly. It identifies the task type and hands off:

| Task type | Agent | Prompt file |
|---|---|---|
| Create/update a FastAPI endpoint | `backend-routers` | `backend-routers-prompt.prompt.md` |
| Create/update SQLAlchemy models or Alembic migrations | `backend-database` | `backend-database-prompt.prompt.md` |
| Set up service logic or external integrations | `backend-integrations` | `backend-integrations-prompt.prompt.md` |
| Generate an implementation plan | `backend-planner` | `backend-planner-prompt.prompt.md` |


If the request spans multiple domains, ask the user to break it into single-task prompts.
