---
mode: agent
agent: backend-planner
name: backend-planner-prompt
description: "Prompt for the backend-planner agent. Generates structured implementation plans for new endpoints, database changes, service integrations, or refactoring."
---

### Requirements

1. **Explore the codebase** to understand current file structure, existing patterns, and conventions.
2. **Produce a numbered step-by-step plan** covering each file change required.
3. **Identify dependencies** between steps (e.g., create model before migration, schemas before endpoints).
4. **Risk assessment** — flag breaking changes, data loss risks, or production impact.
5. **Validation plan** — list `ruff check`, `pytest`, `alembic upgrade head` commands for each stage.

### Constraints

- Do not implement code — output the plan only
- Reference specific file paths relative to repo root
- Follow the existing conventions (route structure, model patterns, error handling)

### Output Format

```
## Implementation Plan: [Title]

### Step 1: [File path]
Action: create | modify | delete
Details: [what to add/change]

### Step 2: ...
...

### Risk Assessment
- [Critical/Medium/Low] risks identified
- [Specific items]

### Validation Checklist
- [ ] `ruff check .` passes
- [ ] `pytest -q` passes
- [ ] `alembic upgrade head` applies cleanly
```

### Usage Template

```
Plan the implementation of [describe task]. 
Consider [constraints or special requirements].
```

### Chat Example

```
User: Plan the implementation of a todo tagging system.
- tag model: id, name, color
- todo_tags association table: todo_id, tag_id
- GET /api/v1/todos?tag=name filter
- POST /api/v1/todos/{id}/tags
- Service function to sync tags on todo update
```

Agent (expected):
- Explores app/models/, app/routers/, app/services/ for existing patterns
- Produces a step-by-step plan listing files to create, modify, and the dependencies between them
- Does not write any code
