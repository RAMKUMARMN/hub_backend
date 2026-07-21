---
mode: agent
agent: backend-integrations
name: backend-integrations-prompt
description: "Prompt for the backend-integrations agent. Creates or updates service layer business logic: LLM (AI service proxy), RAG (AI service proxy), local filesystem storage, JWT auth, document extraction (AI service proxy)."
---

### Requirements

1. **Service Pattern:** Place business logic in `app/services/<domain>_service.py`. Functions accept domain objects (models, schemas) and return results. Services should be stateless (no classes).
2. **LLM Service:** Proxies to the AI service at `settings.ai_service_url`. Use `httpx.AsyncClient` for streaming (SSE) and embedding. Place in `app/services/llm_service.py`.
3. **RAG Service:** Proxies ingest/retrieve/delete to the AI service (which wraps ChromaDB). Place in `app/services/rag_service.py`.
4. **Storage Service:** Local filesystem in `uploads/` directory. S3 support is planned as a TODO. Place in `app/services/storage_service.py`.
5. **Auth Service:** JWT issue/verify (`jose`), password hashing (`bcrypt`). Place in `app/services/auth_service.py`. Google OAuth is config-only, not yet implemented.
6. **Document Service:** Proxies text extraction to the AI service (which handles PDF via PyMuPDF, DOCX via python-docx, OCR via Tesseract). Place in `app/services/document_service.py`.

### Constraints

- Python 3.10+ with async/await for all I/O-bound operations
- Connection details come from Pydantic settings — never hardcoded
- All external calls must have timeout and retry logic
- Errors must be caught and wrapped in domain-specific exceptions
- Integration tests should use test containers or mocks

### Success Criteria

- Service function works when called from a route handler
- External connection handles disconnection and reconnection
- Errors surface as domain-specific exceptions (not raw connection errors)
- Integration test passes (or skips if external service is unavailable)
- Configuration is documented in README

### Usage Template

```
Create/update a [service_name] service for [integration_type]:
- Purpose: [what the service does]
- Endpoint: [connection details]
- [Optional] Retry policy: [retry count, backoff]
- [Optional] Caching: [TTL, cache key pattern]
Show the diff and wait for my confirmation before applying.
```

### Chat Examples

```
User: Add a streaming LLM call that sends a prompt to the AI service and returns the response. Use the existing service pattern.
```

Agent (expected):
- Creates or updates app/services/llm_service.py
- Shows the diff and waits for confirmation before applying

```
User: Set up local file storage for document uploads (no S3 yet).
```

Agent (expected):
- Creates or updates app/services/storage_service.py with upload, download, delete using local filesystem
- Shows the diff and waits for confirmation before applying
