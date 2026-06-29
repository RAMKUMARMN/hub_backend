---
mode: agent
agent: backend-integrations
name: backend-integrations-prompt
description: "Prompt for the backend-integrations agent. Creates or updates service layer business logic and external service integrations: RabbitMQ, Redis, Ollama, ChromaDB, MinIO/S3."
---

### Requirements

1. **Service Pattern:** Place business logic in `app/services/<domain>_service.py`. Functions accept domain objects (models, schemas) and return results. Services should be stateless.
2. **RabbitMQ:** Use aio-pika for async publish/consume. Define queue/exchange topology in `app/services/queue_service.py`. Use `connect_robust` for resilient connections.
3. **Redis:** Use redis-py async for caching. Use `app/services/cache_service.py` with TTL-based expiration. Prefix keys by domain.
4. **Ollama:** Use `httpx.AsyncClient` to call Ollama API. Place in `app/services/llm_service.py`. Handle streaming responses.
5. **ChromaDB:** Use the chromadb Python client. Place in `app/services/rag_service.py`. Support collection create/delete and vector search.
6. **MinIO/S3:** Use boto3 async. Place in `app/services/storage_service.py`. Support upload, download, delete, presigned URLs.

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

### Chat Example

```
User: Create a notification service that publishes messages to a RabbitMQ queue.
- Queue name: notifications
- Exchange: direct
- Message format: { type, recipient, channel, content }
- Retry: 3 attempts with exponential backoff
```

Agent (expected):
- Creates app/services/notification_service.py with publish function
- Shows the diff and waits for confirmation before applying
