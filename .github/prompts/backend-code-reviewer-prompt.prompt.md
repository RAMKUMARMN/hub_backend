---
mode: agent
agent: backend-code-reviewer
name: backend-code-reviewer-prompt
description: "Prompt for the backend-code-reviewer agent. Reviews FastAPI endpoints, database models, service logic, and tests for correctness, security, performance, and best practices."
---

### Requirements

1. **Review each provided file** or changed files for correctness, security, performance, best practices, readability, and migration safety.
2. **Categorize each finding** as `critical`, `warning`, or `suggestion`.
3. **Reference specific line numbers** in files.
4. **Provide a risk summary** and go/no-go recommendation.
5. **Consider the following review dimensions:**

| Dimension | What to check |
|---|---|
| Correctness | Route logic, async/await usage, SQLAlchemy queries, Pydantic validation |
| Security | SQL injection, JWT handling, input sanitization, secret exposure |
| Performance | N+1 queries, missing indexes, sync I/O in async context, pagination |
| Best practices | FastAPI conventions, type hints, dependency injection, error handling |
| Readability | Meaningful names, docstrings, consistent patterns with codebase |
| Migration safety | Downgrade path, data integrity, production impact |

### Constraints

- Do not implement fixes — flag issues for the domain agent to address
- If no issues found, confirm that the code is clean across all dimensions
- Pay special attention to async/await correctness and database session handling

### Output Format

```
## Review: [files reviewed]

### Critical
- [line] [issue description]

### Warnings
- [line] [issue description]

### Suggestions
- [line] [issue description]

### Risk Summary
[go / no-go] — [brief rationale]
```

### Usage Template

```
Review these files for merge readiness:
- [file path 1]
- [file path 2]
Context: [feature purpose, related services]
```

### Chat Example

```
User: Review app/routers/workspaces.py and app/services/workspace_service.py for correctness and security.
```

Agent (expected):
- Reads both files and their dependencies
- Produces structured review with line references and severity
- Provides go/no-go recommendation with rationale
