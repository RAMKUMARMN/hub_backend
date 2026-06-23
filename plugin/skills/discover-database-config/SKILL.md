---

name: discover-database-config
description: Analyze backend database initialization, persistence configuration, and ORM integration.
-----------------------------------------------------------------------------------------------------

# Discover Database Configuration

Analyze database configuration and persistence architecture.

## Focus Areas

* Database Initialization
* Connection Management
* ORM Configuration
* Persistence Dependencies

## Goals

* Discover database startup flow.
* Trace persistence configuration.
* Identify model registration and initialization.

## Output

Return:

* Database configuration map
* Connection lifecycle
* Persistence architecture
* ORM relationships

## Workflow

1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `discoverDatabaseConfig`.
3. Trace configuration sources and initialization flow.
4. Return persistence architecture and dependencies.
