---
name: discover-local-models
description: Inspect local LLM serving infrastructure (Ollama/vLLM) and task-to-model routing.
---

# Discover Local Models

Analyze inference routing and structuring for local LLMs (Qwen, DeepSeek, Florence-2).

## Focus Areas
- Task-to-Model routing logic (e.g., Coding -> Qwen2.5-Coder)
- Ollama/vLLM API integration
- Prompt structuring and injection paths

## Goals
- Map distinct routing paths for reasoning, coding, and vision.
- Verify payload structuring for local model inference.

## Output
Return:
- Model routing classification map
- Inference payload structures

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `search_codebase` for `Ollama`, `vLLM`, `qwen`, `deepseek`, or `florence`.
3. Understand task-based model selection and prompt structuring.
4. Return the compiled model routing schema.
