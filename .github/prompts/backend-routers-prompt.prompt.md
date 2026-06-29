---
mode: agent
agent: backend-routers
name: backend-routers-prompt
description: "Prompt for the backend-routers agent. Creates or updates FastAPI REST endpoints with Pydantic schemas, dependencies, route registration, and tests."
---

### Requirements

1. **Route Structure:** Group endpoints in `app/routers/<domain>.py`. Prefix all routes with `/api/v1/`.
2. **Pydantic Schemas:** Define request bodies and response models using Pydantic v2. Use `from_attributes = True` for ORM mode.
3. **Dependency Injection:** Use FastAPI dependencies for shared concerns (DB session, current user, pagination).
4. **Error Handling:** Return appropriate HTTP status codes (200, 201, 204, 400, 401, 403, 404, 422, 500) with structured error bodies.
5. **Authentication:** Apply JWT auth via the existing `get_current_user` dependency. Use `@router.get("/path", dependencies=[Depends(...)])` for endpoint-level auth.
6. **Tests:** Write tests using `httpx.AsyncClient` with the test database session fixture.

### Constraints

- Python 3.10+ with async FastAPI endpoints
- All endpoints accept and return JSON
- Route handlers are thin — delegate business logic to `app/services/`
- Sensitive data (passwords, tokens) must not appear in error responses or logs
- Use `Depends()` for dependency injection — no global state

### Success Criteria

- Endpoint returns correct status code and response body for valid requests
- Invalid requests return 422 with clear validation messages
- Authentication works (returns 401 for unauthenticated, 403 for unauthorized)
- Endpoint is registered in `app/main.py` router includes
- Test passes with `pytest -q tests/test_<domain>.py`

### Usage Template

```
Add a [METHOD] /api/v1/[domain]/[path] endpoint that:
- Accepts [request schema fields]
- Returns [response schema fields]
- Requires [auth level: public | authenticated | admin]
- Delegates to [service function]
Show the diff and wait for my confirmation before applying.
```

### Chat Example

```
User: Add a GET /api/v1/workspaces endpoint returning all workspaces for the authenticated user.
- Create router in app/routers/workspaces.py
- Schema: WorkspaceRead with id, name, created_at
- Service: workspace_service.get_workspaces(user_id)
- Test with httpx.AsyncClient
```

Agent (expected):
- Creates router, schema, updates main.py, adds test
- Shows the diff and waits for confirmation before applying
