# Hub Backend Quickrefs

This file contains repository-specific quick references, commands, and common prompts for developer productivity.

Repository layout highlights
- `app/routers/` — route definitions grouped by domain
- `app/services/` — business logic and LLM wrappers
- `app/models/` — SQLAlchemy models
- `app/schemas/` — Pydantic schemas
- `alembic/versions/` — DB migrations

Common commands
- Create virtualenv and install:

```bash
python -m venv .venv
.
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

- Run tests:

```bash
pytest -q
```

- Migrations:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Useful prompts for code generation
- "Add a Pydantic v2 model for the `Document` entity and include serialization methods."
- "Generate an Alembic migration to add column `x` to table `y`."
- "Write unit tests for `app/services/document_service.py` covering success and failure cases."

PR review checklist
- Tests added or updated
- Alembic migrations included for DB changes
- Security: validate inputs, avoid naive file handling
