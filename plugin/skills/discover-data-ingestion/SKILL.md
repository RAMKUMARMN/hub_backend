---
name: discover-data-ingestion
description: Map Docling/SmolDocling and Florence-2 parsing layers for document ingestion.
---

# Discover Data Ingestion

Analyze the document processing layer responsible for structure-aware parsing and image understanding.

## Focus Areas
- Text Extraction & Layout Analysis (`Docling`/`SmolDocling`)
- Image & OCR Processing (`Florence-2`)

## Goals
- Document ingestion paths for PDFs, DOCX, CSVs, and Images.
- Verify that structural integrity is maintained.

## Output
Return:
- Ingestion routing map
- Parsing engine handoff schemas

## Workflow
1. Route the hub folder agent to plugin/skills for this specific skill folder saved in the hub folder.
2. Invoke `search_codebase` for `docling` and `florence-2`.
3. Trace extraction routing from upload to normalizer.
4. Return the architecture.
