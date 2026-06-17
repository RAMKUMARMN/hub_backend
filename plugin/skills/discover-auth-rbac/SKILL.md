---
name: discover-auth-rbac
description: Trace JWT/OAuth2 authentication flow, manage tokens, and Role-Based Access Control (RBAC) implementations.
---

# Discover Auth & RBAC

Trace the security boundaries, JWT token management, permission checks, and role restrictions.

## Focus Areas
- Managing JWT token generation, refreshing, and decoding logic
- `OAuth2PasswordBearer` implementations and session validation
- Route-level permission checks and role enforcement (RBAC)

## Goals
- Verify how tokens are minted, refreshed, and managed securely.
- Map token scopes to specific permission checks and user roles stored in the database.
- Ensure strict access boundary mapping.

## Output
Return:
- Authentication middleware flow and JWT management
- Role-to-endpoint permission checks matrix

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `search_codebase` for `jwt.decode`, `OAuth2PasswordBearer`, or permission check functions.
3. Inspect the Auth Service to validate the complete token lifecycle.
4. Trace the RBAC logic to see how endpoints restrict access based on User Roles.
5. Return the permission access matrix and middleware flow.
