---
phase: 06-embedder-migration
plan: "01"
subsystem: embedder
tags: [litellm, vertex-ai, embeddings, sentence-transformers, migration]
dependency_graph:
  requires: []
  provides: [CodeEmbedder-litellm-backend, config-embedding-section-v2]
  affects: [fastcode/embedder.py, fastcode/indexer.py, config/config.yaml]
tech_stack:
  added: [litellm.embedding()]
  removed: [sentence-transformers, torch, platform]
  patterns: [delegate-embed-text-to-embed-batch, task-type-kwarg-for-vertex-ai]
key_files:
  created: []
  modified:
    - fastcode/embedder.py
    - config/config.yaml
    - fastcode/indexer.py
decisions:
  - "litellm.embedding() with task_type kwarg routes to VertexAI without provider-specific client code"
  - "embedding_dim=3072 read from config at init — no HTTP call at init time"
  - "embed_text() defaults task_type to RETRIEVAL_QUERY so retriever.py callers require zero changes"
  - "item[\"embedding\"] dict-style access used (not item.embedding) for litellm version safety"
  - "__init__.py import platform is pre-existing for tokenizer env var setup — out of scope"
metrics:
  duration: "3min"
  completed: "2026-02-25"
  tasks_completed: 3
  files_modified: 3
---

# Phase 06 Plan 01: Embedder Migration to litellm/VertexAI Summary

**One-liner:** CodeEmbedder rewritten to call litellm.embedding() with vertex_ai/gemini-embedding-001, eliminating torch/sentence-transformers from the runtime entirely.

## What Was Built

Replaced the sentence-transformers backend in `CodeEmbedder` with a litellm-based backend that routes to VertexAI's `gemini-embedding-001` model. The public API surface is preserved — `embed_text`, `embed_batch`, `embed_code_elements`, `compute_similarity`, `compute_similarities`, `_prepare_code_text` — with two additions: both `embed_text` and `embed_batch` now accept an optional `task_type` kwarg (default: `RETRIEVAL_QUERY`) to distinguish query vs document embeddings.

Updated `config/config.yaml` to replace the sentence-transformers embedding block with the VertexAI model config, and made a 1-line change in `fastcode/indexer.py` to pass `task_type="RETRIEVAL_DOCUMENT"` when embedding repo overviews.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite CodeEmbedder to use litellm.embedding() | 8014728 | fastcode/embedder.py |
| 2 | Update config/config.yaml embedding section and indexer.py call site | 19534b2 | config/config.yaml, fastcode/indexer.py |
| 3 | Verify full import chain and run import smoke check | (no commit — verification only) | — |

## Key Changes

### fastcode/embedder.py

- **Removed:** `import platform`, `import torch`, `from sentence_transformers import SentenceTransformer`
- **Added:** `import litellm`, `from tqdm import tqdm`
- **`__init__()`:** Reads `embedding_dim` from config (default 3072), stores `model_name`, `batch_size`, `normalize` — no HTTP calls, no model download
- **`embed_batch()`:** Calls `litellm.embedding(model=self.model_name, input=batch, task_type=task_type)`, extracts `item["embedding"]` dict-style, applies L2 normalization with div-by-zero guard
- **`embed_text()`:** Delegates to `embed_batch([text], task_type=task_type)[0]`
- **`embed_code_elements()`:** Passes `task_type="RETRIEVAL_DOCUMENT"` to embed_batch
- **Removed:** `_load_model()` method entirely
- **Unchanged:** `compute_similarity()`, `compute_similarities()`, `_prepare_code_text()`

### config/config.yaml

- **Removed keys:** `device`, `max_seq_length`, sentence-transformers model and alt-model comments
- **New model:** `vertex_ai/gemini-embedding-001`
- **New key:** `embedding_dim: 3072`
- Retained: `batch_size: 32`, `normalize_embeddings: true`

### fastcode/indexer.py

- Line 369 in `_save_repository_overview()`: `embed_text(overview_text)` → `embed_text(overview_text, task_type="RETRIEVAL_DOCUMENT")`

## Deviations from Plan

### Scope Observation (Not Fixed)

`fastcode/__init__.py` contains `import platform` for setting tokenizer parallelism env vars on macOS (`TOKENIZERS_PARALLELISM`, `OMP_NUM_THREADS`, etc.). This pre-existed the embedder migration and is unrelated to sentence-transformers. The plan's grep check `grep -r "import platform" fastcode/` would flag this, but it is intentionally out of scope per deviation rules (pre-existing, different file, different purpose). Deferred to `deferred-items.md`.

## Verification Results

All automated checks passed:
- `embedder.py` has no torch/sentence_transformers/platform imports
- litellm and task_type present in embedder.py
- `config/config.yaml` embedding section: model=vertex_ai/gemini-embedding-001, embedding_dim=3072, no device/max_seq_length
- `indexer.py` has `embed_text(overview_text, task_type="RETRIEVAL_DOCUMENT")`
- `from fastcode.embedder import CodeEmbedder` imports with no torch/sentence-transformers
- `CodeEmbedder(config)` instantiates: model=vertex_ai/gemini-embedding-001, dim=3072, no `device` attribute

## Self-Check: PASSED

All required files exist:
- fastcode/embedder.py - FOUND
- config/config.yaml - FOUND
- fastcode/indexer.py - FOUND
- .planning/phases/06-embedder-migration/06-01-SUMMARY.md - FOUND

All commits exist:
- 8014728 (Task 1: feat(06-01): rewrite CodeEmbedder) - FOUND
- 19534b2 (Task 2: feat(06-01): update config embedding section) - FOUND
