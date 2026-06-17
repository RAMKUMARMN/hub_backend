---
name: trace-event-publishers
description: Trace Event Streaming routing (Kafka) and telemetry publishers.
---

# Trace Event Publishers

Analyze event publishers and telemetry routing used for observability.

## Focus Areas
- Kafka producer routing
- Event topic structuring (User Events, Audit Events)
- OpenTelemetry/Prometheus metric hooks

## Goals
- Map the trigger points where structured events are routed to Kafka.
- Verify event payload formats.

## Output
Return:
- Topics and metrics routing map
- Event structuring and payload schema

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `search_codebase` for `kafka`, `events`, `telemetry`, or `prometheus`.
3. Trace how events are structured and dispatched.
4. Return findings.
