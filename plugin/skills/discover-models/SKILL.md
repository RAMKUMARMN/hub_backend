---
name: discover-models
description: Inspect Aurora PostgreSQL schemas, ORM structuring, and table relationships.
---

# Discover Relational DB & ORM

Analyze the SQLAlchemy/SQLModel definitions establishing the ORM layer and structuring database relationships.

## Focus Areas
- ORM configurations and relational structuring
- Foreign key dependencies and model relations (Users, Metadata, Subscriptions)
- FastAPI database session injection

## Goals
- Map the permanent data structures and ORM relations completely.
- Verify cascading deletes and foreign key bounds.
- Ensure strict read-only analysis.

## Output
Return:
- ORM entity-relationship map
- Complete table schema and relations structure

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `search_codebase` for ORM models (SQLAlchemy/SQLModel).
3. Use `read_file_secure` to thoroughly map all ORM relations and database structuring.
4. Return the compiled relational schemas.
