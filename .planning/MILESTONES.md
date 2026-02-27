# Milestones

## v1.0 LiteLLM Provider Migration (Shipped: 2026-02-25)

**Phases completed:** 5 phases, 10 plans | 70 files changed | +9,792 / −1,296 lines | 65 commits | 12 days

**Key accomplishments:**
1. Centralized `fastcode/llm_client.py` — single `completion()`, `completion_stream()`, `count_tokens()`, `DEFAULT_MODEL` path for all LLM callers
2. All 4 non-streaming callers migrated (`query_processor.py`, `repo_selector.py`, `repo_overview.py`, `iterative_agent.py`) — provider dispatch branches removed
3. `answer_generator.py` fully migrated: streaming, non-streaming, and all 6 token-counting call sites wired through litellm
4. `llm_utils.py` deleted; `litellm.drop_params = True` supersedes its max_tokens fallback logic
5. VertexAI ADC smoke test + streaming smoke test confirmed live via real GCP credentials (13/13 passing)
6. Token counting and context truncation accurate for Gemini models via `litellm.token_counter()`

**Archive:** `.planning/milestones/v1.0-ROADMAP.md`

---


## v1.1 VertexAI Embedding Migration (Shipped: 2026-02-25)

**Phases completed:** 2 phases, 3 plans | 2 days

**Key accomplishments:**
1. `fastcode/embedder.py` rewritten — sentence-transformers backend replaced with `litellm.embedding()` calling `vertex_ai/gemini-embedding-001`
2. Asymmetric task_type pairing: `RETRIEVAL_DOCUMENT` at index time, `RETRIEVAL_QUERY` at search time — consistent with Gemini embedding API design
3. `sentence-transformers`, `torch`, and all transitively-required GPU/CPU packages removed from all dependency manifests
4. Live ADC smoke test confirms shape `(3072,)`, L2 norm 1.0, full round-trip through VertexAI embedding API

**Archive:** `.planning/milestones/v1.1-ROADMAP.md`

---


## v1.2 uv Migration & Tech Debt Cleanup (Shipped: 2026-02-27)

**Phases completed:** 3 phases, 6 plans | 1 day

**Key accomplishments:**
1. `requirements.txt` replaced with `pyproject.toml` + `uv.lock` (160 packages, hatchling editable install, dev deps in `[dependency-groups] dev`)
2. Dockerfile rewritten with uv two-layer cache pattern — deps layer cached independently from source; `UV_NO_DEV=1` excludes pytest from production image
3. Dead `fastcode/__init__.py` OS-detection block removed; `task_type` now explicit at `retriever.py:415` and `:734`
4. `MODEL` env var eliminated — all 5 LLM callers uniformly read `llm_client.DEFAULT_MODEL` (sourced from `LITELLM_MODEL`)
5. Live smoke tests confirm: `CODE_RETRIEVAL_QUERY` accepted by gemini-embedding-001; `_stream_with_summary_filter()` produces no SUMMARY tag leakage

**Archive:** `.planning/milestones/v1.2-ROADMAP.md`

---

