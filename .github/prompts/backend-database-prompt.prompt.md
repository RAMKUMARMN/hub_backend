---
mode: agent
agent: backend-database
name: backend-database-prompt
description: "Prompt for the backend-database agent. Creates or updates SQLAlchemy models, Pydantic schemas, and Alembic migrations with safety guards."
---

### Requirements

1. **Models:** Use SQLAlchemy 2.0 async style with `DeclarativeBase`. Use UUIDs for primary keys. Include `created_at` and `updated_at` timestamps. Use soft deletes where applicable.
2. **Relationships:** Define foreign keys with `ForeignKey`, relationships with `relationship()`. Use `back_populates` for bidirectional navigation.
3. **Indexes:** Add indexes on foreign keys and frequently queried columns.
4. **Migrations:** Generate via `alembic revision --autogenerate -m "message"`. Review the generated script for correctness. Ensure downgrade is implemented.
5. **Schemas:** Create matching Pydantic v2 schemas (Create, Read, Update, List). Use `from_attributes = True` for ORM-to-schema conversion.

### Constraints

- PostgreSQL dialect — use dialect-specific types where needed (ARRAY, JSONB, UUID)
- All models inherit from `app.database.Base`
- Migrations must have both upgrade() and downgrade() implemented
- Do not auto-apply migrations — show the diff and wait for confirmation
- Production migrations require `CONFIRM_PROD_MIGRATION` token

### Success Criteria

- Model compiles with `python -c "from app.models import *"`
- Migration script generates without errors: `alembic revision --autogenerate`
- Migration applies and rolls back cleanly: `alembic upgrade head` then `alembic downgrade -1`
- Pydantic schemas validate correct data and reject invalid data
- Foreign keys and relationships work in queries

### Usage Template

```
Create/update a [model_name] model with:
- Columns: [list with types, constraints, defaults]
- Relationships: [list with foreign keys and back_populates]
- [Optional] Migration message: [message]
- [Optional] Schemas: [Create, Read, Update, List]
Show the diff and wait for my confirmation before applying.
Do NOT auto-apply migrations without explicit approval.
```

### Chat Example

```
User: Add a workspace table.
- id (UUID PK), name (VARCHAR 255, required), description (TEXT, optional)
- owner_id (FK to users, required), created_at, updated_at
- Create Read and Create schemas
- Generate a migration
```

Agent (expected):
- Creates model in app/models/workspace.py, schemas, generates migration
- Shows the diff and waits for confirmation before applying
- Does not apply the migration automatically
