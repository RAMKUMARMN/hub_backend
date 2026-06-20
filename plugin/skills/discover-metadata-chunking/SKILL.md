---
name: discover-metadata-chunking
description: Trace Key Information Extraction, NER, and Smart Chunking before embedding.
---

# Discover Metadata & Smart Chunking

Analyze how raw text is categorized, tagged, and sectioned.

## Focus Areas
- Document Classification and Key Information Extraction (NER)
- Smart Chunking logic (Language detection, sliding window overlap)

## Goals
- Document chunk size, overlap parameters, and semantic structuring.
- Verify metadata attachment to chunks.

## Output
Return:
- Chunking structuring parameters
- Extracted metadata payload

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `search_codebase` for chunking algorithms, `NER`, or `metadata`.
3. Trace the pre-processing loop prior to embedding.
4. Return the compiled chunking structure.
