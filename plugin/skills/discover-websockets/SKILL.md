---
name: discover-websockets
description: Map the real-time Chat Service, WebSockets, and Server-Sent Events (SSE) streaming infrastructure.
---

# Discover WebSockets & SSE

Analyze the backend infrastructure responsible for maintaining active connection pools and streaming real-time tokens.

## Focus Areas
- `WebSocketEndpoint` connection managers
- SSE `StreamingResponse` generators
- Conversation session routing

## Goals
- Map how incoming real-time messages are routed.
- Trace the non-blocking SSE path used to stream local LLM tokens.

## Output
Return:
- WebSocket connection routing map
- SSE streaming generator schemas

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `search_codebase` for `WebSocketEndpoint`, `accept()`, or `StreamingResponse`.
3. Trace the Chat Service logic to understand real-time routing.
4. Return the streaming architecture layout.
