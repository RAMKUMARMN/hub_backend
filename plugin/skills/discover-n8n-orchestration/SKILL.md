---
name: discover-n8n-orchestration
description: Map n8n workflow orchestration, webhooks, and automation routing.
---

# Discover n8n Orchestration

Analyze the n8n layer controlling multi-step workflows, automation, and intelligent routing.

## Focus Areas
- n8n webhook endpoints in FastAPI routing
- JSON workflow definition structuring
- Orchestration for document summarization, cron tasks, and human approvals

## Goals
- Map the complete handoff from FastAPI routing to n8n.
- Validate retry & error handling structure inside the workflows.

## Output
Return:
- n8n trigger and routing map
- Workflow structure tree

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `search_codebase` using patterns like `n8n` or `webhook`.
3. Browse directory for n8n export JSONs and trace routing nodes.
4. Compile and return the n8n routing map.
