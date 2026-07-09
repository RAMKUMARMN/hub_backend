---
mode: agent
agent: backend-master-api-reviewer
name: backend-master-api-reviewer-prompt
description: "Prompt for the backend-master-api-reviewer agent. Detects breaking changes in routers/ and schemas/ by cross-referencing client contract definitions in hub_mobile and hub_frontend."
---

### Requirements

1. **Read the changed files** in `app/routers/` or `app/schemas/`.
2. **Cross-reference every field** against the client contract definitions:
   - `hub_mobile/lib/models/user.dart` — `User.fromJson` parses: `id`, `email`, `full_name`, `phone`, `avatar_url`, `is_admin`, `created_at`
   - `hub_mobile/lib/models/todo.dart` — `Todo.fromJson` parses: `id`, `title`, `description`, `completed`, `due_date`, `created_at`
   - `hub_mobile/lib/models/document.dart` — `Document.fromJson` parses: `id`, `filename`, `file_type`, `file_size`, `processed`, `chunk_count`, `created_at`
   - `hub_mobile/lib/models/message.dart` — `ChatSession.fromJson` parses: `id`, `title`, `created_at`, `updated_at`; `ChatMessage.fromJson` parses: `id`, `session_id`, `role`, `content`, `created_at`
   - `hub_frontend/src/types/index.ts` — interfaces: `User`, `ChatSession`, `ChatMessage`, `Document`, `Todo`, `TokenResponse`
   - `hub_frontend/src/app/queues/page.tsx` — inline `Job`, `QueueStat` interfaces
   - `hub_frontend/src/app/poll/page.tsx` — inline `PollPayload` interface
3. **Detect breaking changes** per the criteria below.
4. **Classify** as `CRITICAL: BREAKING CHANGE` or `NON-BREAKING`.
5. **Provide a client-side mock update snippet** for every breaking change.

### Breaking change criteria

A change is **breaking** if:

| Criterion | Example |
|---|---|
| Field removed | Deleting `phone` from `UpdateProfileRequest` when mobile sends it |
| Field renamed | Changing `full_name` to `fullname` — mobile `fromJson` tries `json['full_name']` → null |
| Type changed | `file_size` from `int` to `string` — mobile does `(json['file_size'] as num?)?.toInt()` → crash |
| Required → optional | Making `email` nullable — mobile does `json['email'] as String` → runtime cast error |
| Optional → required (no default) | Making `avatar_url` required — mobile has `as String?` → null-safe, but frontend has `string \| null` → fine |
| Path param renamed | `{id}` to `{todo_id}` — mobile calls `/todos/$id` → 404 |
| Query param removed | Removing `?completed=` filter — mobile uses it for todo filtering |
| Status code changed | `DELETE /todos/{id}` returning 200 instead of 204 — mobile doesn't check, low risk |
| Response shape restructured | Wrapping response in `{ data: [...] }` instead of returning the array directly |

### Output format

```
## Master API Review: [files reviewed]

### CRITICAL: BREAKING CHANGE
- [file:line] [field] — [what changed] — [which client(s) affected]

  Client-side update (mobile):
  ```dart
  // hub_mobile/lib/models/<model>.dart
  // Before:
  // After:
  ```

  Client-side update (frontend):
  ```typescript
  // hub_frontend/src/types/index.ts
  // Before:
  // After:
  ```

### Warnings (non-breaking but notable)
- [file:line] [field] — [what changed] — [why it's safe]

### Summary
[PASS / CRITICAL: BREAKING CHANGE] — [risk assessment]
```

### Contract reference

Full field mapping:

| Backend schema | Mobile `fromJson` key | Frontend TS field |
|---|---|---|
| `UserResponse` | `id`, `email`, `full_name`, `phone?`, `avatar_url?`, `is_admin??`, `created_at` | `id`, `email`, `full_name`, `phone?`, `avatar_url?`, `is_admin`, `created_at` |
| `TodoResponse` | `id`, `title`, `description?`, `completed??`, `due_date?`, `created_at??` | `id`, `title`, `description?`, `completed`, `due_date?`, `created_at`, `updated_at` |
| `SessionResponse` | `id`, `title`, `created_at`, `updated_at` | `id`, `title`, `created_at`, `updated_at` |
| `MessageResponse` | `id`, `session_id`, `role`, `content`, `created_at` | `id`, `session_id`, `role`, `content`, `created_at` |
| `DocumentResponse` | `id`, `filename`, `file_type??`, `file_size??`, `processed??`, `chunk_count??`, `created_at??` | `id`, `filename`, `file_type`, `file_size`, `processed`, `created_at` |

(`?` = nullable in source, `??` = nullable with default fallback in `fromJson`)

### Constraints

- Do not modify any files — this agent is read-only
- If the change does not touch `routers/` or `schemas/`, state "No API contract changes detected."
- If client contract files are not found, note it in the review
- Always include the `CRITICAL: BREAKING CHANGE` prefix when a breaking change is detected
- The client-side snippet must be copy-paste ready

### Usage template

```
Review these API changes for breaking changes:
- [file path 1]
- [file path 2]
Context: [feature purpose]
```

### Chat example

```
User: Review the changes to app/schemas/todo.py. The 'description' field is being removed from TodoResponse.
```

Agent (expected):
- Loads hub_mobile Todo model: sees `description` parsed at line 22
- Loads hub_frontend Todo type: sees `description: string | null` at line 40
- Marks as CRITICAL: BREAKING CHANGE
- Provides update snippet for both clients
