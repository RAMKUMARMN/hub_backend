---
name: discover-guardrails-safety
description: Validate Content Safety structuring, PII/PHI Detection, and output validation.
---

# Discover Guardrails & Safety

Analyze output validation, permission checks for content, and safety routing.

## Focus Areas
- PII / PHI Detection structuring
- Content Safety filters
- Hallucination reduction checks

## Goals
- Document the exact data sanitization structures applied to outputs.
- Verify safety guardrail routing before user delivery.

## Output
Return:
- Safety validation ruleset structure
- PII sanitization routing map

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `search_codebase` for `safety`, `pii`, or `validation`.
3. Analyze Response Generation interceptors and content permission checks.
4. Return the compiled safety ruleset.
