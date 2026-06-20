---
name: trace-hybrid-retrieval
description: Trace ChromaDB Vector Search, BM25 Keyword Search, and Cross-Encoder Re-ranking.
---

# Trace Hybrid Retrieval

Analyze the RAG pipeline to ensure high-accuracy semantic structuring and context assembly.

## Focus Areas
- ChromaDB integrations and vector structuring
- Semantic vs. Keyword (BM25) search execution
- `bge-reranker-large` cross-encoder integration

## Goals
- Verify the fusion mechanism of retrieved chunks.
- Confirm ChromaDB vector schema configurations.

## Output
Return:
- Retrieval pipeline routing and step flow
- Reranking validation metrics

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `search_codebase` for `chroma`, `bm25`, and `rerank`.
3. Trace the retrieval routing logic and fusion mechanism.
4. Return the complete retrieval flow.
