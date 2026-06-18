---
name: discover-memory-context
description: Inspect Session Management, Long-term Memory caching, and Context Compression.
---

# Discover Memory & Context

Analyze conversation structuring, Redis caching, and Aurora history.

## Focus Areas
- Chat History retrieval and Redis hot routing
- Long-term Memory summarization (Aurora)
- Context Compression algorithms

## Goals
- Document how active session structures are managed.
- Verify threshold logic for compression routing.

## Output
Return:
- Memory management routing map
- Context structuring rules

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `search_codebase` for `memory`, `compression`, or `history`.
3. Trace how previous context structures are injected into new prompts.
4. Return the memory architecture map.
