---

name: discover-schemas
description: Map backend request/response schemas, validation models, and DTO relationships.
--------------------------------------------------------------------------------------------

# Discover Schemas

Analyze the schema layer used throughout the SmartHub backend.

## Focus Areas

* Request Schemas
* Response Schemas
* Validation Models
* DTO Relationships

## Goals

* Identify schema ownership.
* Trace request and response model usage.
* Map validation flow dependencies.

## Output

Return:

* Schema inventory
* Request/response mappings
* Validation relationships
* Cross-service schema dependencies

## Workflow

1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `discoverSchemas`.
3. Trace schema references across routes and services.
4. Return schema architecture and dependencies.
