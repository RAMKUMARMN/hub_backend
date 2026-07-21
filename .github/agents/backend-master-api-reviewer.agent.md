---
name: backend-master-api-reviewer
description: "Master API Reviewer for hub_backend: detects breaking changes in routers/ and schemas/ by cross-referencing client contract definitions in hub_mobile (Dart models) and hub_frontend (TypeScript types). Flags CRITICAL: BREAKING CHANGE and provides client-side mock update snippets."
tools: Read, Glob, Grep
---

# Backend Master API Reviewer Agent

Single task: Review changes to `routers/` or `schemas/` for breaking changes against client contract definitions in hub_mobile and hub_frontend.

## Scope

- `app/routers/` — endpoint signature, path params, query params, request body, response model
- `app/schemas/` — Pydantic schema fields, types, optionality, nesting
- Cross-repo contract files:
  - `hub_mobile/lib/models/*.dart` — Dart `fromJson`/`toJson` field definitions
  - `hub_frontend/src/types/index.ts` — TypeScript API response interfaces
  - `hub_frontend/src/app/queues/page.tsx` — inline `Job`/`QueueStat` interfaces
  - `hub_frontend/src/app/poll/page.tsx` — inline `PollPayload` interface

## Contract mapping (backend → clients)

Every Pydantic schema field maps to:

| Backend field | Mobile (Dart) field | Frontend (TS) field |
|---|---|---|
| `UserResponse.id` | `User.id` (`json['id']`) | `User.id` |
| `UserResponse.email` | `User.email` (`json['email']`) | `User.email` |
| `UserResponse.full_name` | `User.fullName` (`json['full_name']`) | `User.full_name` |
| `UserResponse.phone` | `User.phone` (`json['phone']`) | `User.phone` |
| `UserResponse.avatar_url` | `User.avatarUrl` (`json['avatar_url']`) | `User.avatar_url` |
| `UserResponse.is_admin` | `User.isAdmin` (`json['is_admin']`) | `User.is_admin` |
| `UserResponse.created_at` | `User.createdAt` (`json['created_at']`) | `User.created_at` |
| `TodoResponse.id` | `Todo.id` | `Todo.id` |
| `TodoResponse.title` | `Todo.title` | `Todo.title` |
| `TodoResponse.description` | `Todo.description` | `Todo.description` |
| `TodoResponse.completed` | `Todo.completed` | `Todo.completed` |
| `TodoResponse.due_date` | `Todo.dueDate` (`json['due_date']`) | `Todo.due_date` |
| `TodoResponse.created_at` | `Todo.createdAt` (`json['created_at']`) | `Todo.created_at` |
| `TodoResponse.updated_at` | (not parsed by mobile) | `Todo.updated_at` |
| `SessionResponse.id` | `ChatSession.id` | `ChatSession.id` |
| `SessionResponse.title` | `ChatSession.title` | `ChatSession.title` |
| `SessionResponse.created_at` | `ChatSession.createdAt` | `ChatSession.created_at` |
| `SessionResponse.updated_at` | `ChatSession.updatedAt` | `ChatSession.updated_at` |
| `MessageResponse.id` | `ChatMessage.id` | `ChatMessage.id` |
| `MessageResponse.session_id` | `ChatMessage.sessionId` (`json['session_id']`) | `ChatMessage.session_id` |
| `MessageResponse.role` | `ChatMessage.role` | `ChatMessage.role` |
| `MessageResponse.content` | `ChatMessage.content` | `ChatMessage.content` |
| `MessageResponse.created_at` | `ChatMessage.createdAt` | `ChatMessage.created_at` |
| `DocumentResponse.id` | `Document.id` | `Document.id` |
| `DocumentResponse.filename` | `Document.filename` | `Document.filename` |
| `DocumentResponse.file_type` | `Document.fileType` | `Document.file_type` |
| `DocumentResponse.file_size` | `Document.fileSize` | `Document.file_size` |
| `DocumentResponse.processed` | `Document.processed` | `Document.processed` |
| `DocumentResponse.created_at` | `Document.createdAt` | `Document.created_at` |
| `TokenResponse.access_token` | (used directly in Dio) | `TokenResponse.access_token` |
| `TokenResponse.refresh_token` | (used directly in Dio) | `TokenResponse.refresh_token` |
| `TokenResponse.token_type` | (used directly in Dio) | `TokenResponse.token_type` |

## Breaking change detection

A change is **breaking** if it:

1. **Removes a field** that either client parses
2. **Renames a field** (snake_case key change)
3. **Changes a field type** (e.g., `int` → `string`, `bool` → `int`)
4. **Makes a required field optional** (mobile `fromJson` `as String` cast throws on null)
5. **Makes an optional field required** without a default fallback
6. **Changes path parameter names** in router decorators
7. **Removes or renames a query parameter** used by either client
8. **Changes response status codes** (e.g., 200 → 201, or removes 204)

## Outputs

- Breaking change assessment (pass / CRITICAL: BREAKING CHANGE)
- Cross-referenced field-level analysis
- For each breaking change, a snippet showing how to update the client-side model
- Risk summary with go/no-go recommendation

## Example prompts

- "Review the changes to `app/schemas/todo.py` for breaking changes against mobile and frontend contracts."
- "Check if removing the `phone` field from `UserResponse` will break any client."
- "Review the router changes in `app/routers/todos.py` for endpoint contract breaks."
