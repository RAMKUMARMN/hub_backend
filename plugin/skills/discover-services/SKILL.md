---
name: discover-services
description: Inspect synchronous Core Business Services (User, Document, Task), CRUD operations, and metadata structuring.
---

# Discover Core Services & CRUD

Analyze the synchronous business logic layers handling foreground data processing, external cloud storage handoffs (AWS S3), and database CRUD operations.

## Focus Areas
- Core Service controllers (User Service, Document Service, Task Service)
- Database CRUD operations and data structuring
- Synchronous business logic (file validation, upload management)
- Complete structuring of metadata payloads before background/n8n handoff

## Goals
- Trace data reception, validation, and CRUD routing within the Service Layer.
- Track precise data structuring and metadata creation.
- Map the synchronous-to-asynchronous boundary (where Core Services hand off to workflows).

## Output
Return:
- Service controller responsibilities map
- Complete CRUD routing and data structuring maps
- Cloud storage integration points

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Identify the core service controllers (User, Document, Task) and their CRUD routing using \`search_codebase\`.
3. Use \`read_file_secure\` to trace business logic, AWS S3 uploads, and data structuring.
4. Compile the complete Service Layer responsibilities and CRUD map.
`