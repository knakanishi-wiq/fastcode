# Roadmap: FastCode — LiteLLM Provider Migration

## Milestones

- ✅ **v1.0 LiteLLM Provider Migration** — Phases 1–5 (shipped 2026-02-25)
- 🔄 **v1.1 VertexAI Embedding Migration** — Phases 6–7 (in progress)

## Phases

<details>
<summary>✅ v1.0 LiteLLM Provider Migration (Phases 1–5) — SHIPPED 2026-02-25</summary>

- [x] Phase 1: Config and Dependencies (1/1 plans) — completed 2026-02-24
- [x] Phase 2: Core Infrastructure (2/2 plans) — completed 2026-02-24
- [x] Phase 3: Non-Streaming Migration (4/4 plans) — completed 2026-02-24
- [x] Phase 4: Streaming Migration and Finalization (2/2 plans) — completed 2026-02-25
- [x] Phase 5: Fix answer_generator.py Wiring and Cleanup (1/1 plan) — completed 2026-02-25

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
|-------|-----------|----------------|----------|------------|
| 1. Config and Dependencies | v1.0 | 1/1 | Complete | 2026-02-24 |
| 2. Core Infrastructure | v1.0 | 2/2 | Complete | 2026-02-24 |
| 3. Non-Streaming Migration | v1.0 | 4/4 | Complete | 2026-02-24 |
| 4. Streaming Migration and Finalization | v1.0 | 2/2 | Complete | 2026-02-25 |
| 5. Fix answer_generator.py Wiring | v1.0 | 1/1 | Complete | 2026-02-25 |
| 6. Embedder Migration | v1.1 | 0/1 | Pending | — |
| 7. Dependency Cleanup and Smoke Test | v1.1 | 0/1 | Pending | — |

---

## v1.1 VertexAI Embedding Migration

### Phase 6: Embedder Migration

**Goal:** Replace the sentence-transformers backend in `fastcode/embedder.py` with `litellm.embedding()` calling `vertex_ai/gemini-embedding-001`. Update config and the one indexer.py call site that embeds repo overviews.

**Delivers:**
- `fastcode/embedder.py` — `CodeEmbedder` uses `litellm.embedding()` with `task_type` support; no torch/sentence-transformers imports
- `config/config.yaml` — embedding section updated: new model, `embedding_dim: 3072`, `device`/`max_seq_length` removed
- `fastcode/indexer.py` — 1-line change: `embed_text(overview_text, task_type="RETRIEVAL_DOCUMENT")`

**Files changed:** `fastcode/embedder.py`, `config/config.yaml`, `fastcode/indexer.py`

**Success criteria:**
- `from fastcode.embedder import CodeEmbedder` does not import torch or sentence_transformers
- `embed_batch(["hello"])` returns ndarray shape `(1, 3072)` against real VertexAI
- `embed_code_elements([...])` uses `RETRIEVAL_DOCUMENT`; `embed_text(q)` defaults to `RETRIEVAL_QUERY`
- Existing callers in `retriever.py` require zero changes

---

### Phase 7: Dependency Cleanup and Smoke Test

**Goal:** Remove sentence-transformers from the dependency tree, clean up Dockerfile and main.py, add a smoke test that validates embedding via ADC.

**Delivers:**
- `requirements.txt` — `sentence-transformers` removed
- `Dockerfile` — pre-bake model download line removed
- `main.py` — default model string updated to `vertex_ai/gemini-embedding-001`
- `tests/test_embedder_smoke.py` — new smoke test (skips without `VERTEXAI_PROJECT`)

**Files changed:** `requirements.txt`, `Dockerfile`, `main.py`, `tests/test_embedder_smoke.py`

**Success criteria:**
- `pip install -r requirements.txt` does not install sentence-transformers or torch
- `docker build` completes without downloading any embedding model
- Smoke test skips cleanly in CI; passes with real GCP credentials
- No remaining `sentence-transformers/` strings in `fastcode/` source

---
