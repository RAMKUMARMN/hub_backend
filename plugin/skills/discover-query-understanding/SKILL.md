---
name: discover-query-understanding
description: Trace Intent Detection, Query Classification, and Query Expansion routing logic.
---

# Discover Query Understanding

Analyze how user inputs are parsed, classified, and routed to retrieval strategies.

## Focus Areas
- Intent Detection models or rule engines
- Query Classification algorithms
- Multi-step parsing logic

## Goals
- Document how the system distinguishes intents (e.g., General vs. Coding vs. Medical).
- Map the decision tree that triggers the workflow router.

## Output
Return:
- Intent classification and routing matrix
- Query expansion strategy

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `search_codebase` for `intent`, `classification`, or `expansion`.
3. Use `read_file_secure` to trace how the raw user query is routed.
4. Return the classification matrix.
