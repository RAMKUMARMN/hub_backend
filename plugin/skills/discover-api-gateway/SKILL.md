---
name: discover-api-gateway
description: Extract FastAPI router definitions, Nginx reverse proxy connections, and routing logic.
---

# Discover API Gateway

Analyze the FastAPI entry points, request validation layers, and routing structure.

## Focus Areas
- `APIRouter` endpoint registrations and API access mapping
- Pydantic payload validation models
- Middleware decorators and Nginx handoffs
- Routing configuration across the gateway

## Goals
- Document all foreground communication endpoints and their routing trees.
- Validate expected input/output schemas for the API access.
- Ensure UI/Next.js code is strictly ignored.

## Output
Return:
- Endpoint schema layout and API routing map
- Response structure maps

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `search_codebase` for `@app.get`, `@router.`, or `RateLimiter`.
3. Use `read_file_secure` to analyze payload validation and routing logic.
4. Trace the routing logic from the API Gateway down to Core Controllers.
5. Compile baseline payload parameters and return findings.
