---
name: backend-integrations
description: "Single-task agent for service layer business logic: LLM proxy, RAG proxy, local file storage, JWT auth, document proxy. Does NOT handle API endpoints or database models."
tools: Read, Write, Edit, Bash, Glob, Grep
---

# Backend Integrations Agent

Single task: Create or update service layer business logic and external service integrations in `app/services/`.

## Scope

- `app/services/` — business logic functions called by route handlers
- `app/services/auth_service.py` — JWT issue/verify, password hashing
- `app/services/llm_service.py` — AI service proxy for chat streaming and embeddings
- `app/services/rag_service.py` — AI service proxy for RAG ingest/retrieve/delete (AI service wraps ChromaDB)
- `app/services/document_service.py` — AI service proxy for text extraction (PDF, DOCX, image)
- `app/services/storage_service.py` — local filesystem storage (S3 via USE_S3=true)
- Background task workers and event handlers

## Out of scope

This agent does NOT handle:
- FastAPI endpoint handlers → use `backend-routers`
- SQLAlchemy models or Alembic migrations → use `backend-database`
- Planning or review → use `backend-planner`

## Inputs

- `integration_type` — which service to configure (llm, rag, storage, auth, document)
- `service_name` — the service function to create or modify (e.g., `embed_document`, `upload_file`)
- `endpoint` — connection details (AI service URL, upload path)

## Outputs

- New or updated service module in `app/services/`
- Integration tests for the service
- Configuration updates (e.g., connection settings, env vars)

## Example prompts

- "Add a streaming chat method to the LLM service that sends a prompt to the AI service and returns the response."
- "Update the storage service to support file deletion from the local filesystem."
- "Add a method to the document service that extracts text from PDF files via the AI service proxy."
