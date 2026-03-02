# FastCode — LiteLLM Provider Migration

## What This Is

FastCode is a code intelligence backend (RAG pipeline + agentic retrieval) that routes all LLM and embedding calls through litellm, enabling VertexAI on GCP via Application Default Credentials. v1.0 migrated all five LLM call sites to a centralized `fastcode/llm_client.py`. v1.1 completed the GCP-native story by replacing the local sentence-transformers embedding backend with VertexAI `gemini-embedding-001` via litellm — eliminating torch/sentence-transformers from the dependency tree entirely. v1.2 modernized the packaging system (pyproject.toml + uv.lock + uv Dockerfile) and closed all remaining v1.1 tech debt. v1.3 replaced the pkl/rank_bm25 BM25 backend with SQLite FTS5 and migrated the embedding cache from DiskCache to SQLite — consolidating all persistent state into a single `.db` file and removing two external dependencies.

## Core Value

All LLM and embedding calls in FastCode route through litellm, so the system works fully on VertexAI via ADC without maintaining any provider-specific client code.

## Requirements

### Validated

- ✓ Replace direct openai/anthropic clients with litellm across all LLM call sites — v1.0
- ✓ VertexAI support via litellm with ADC authentication (`gcloud auth application-default login`) — v1.0
- ✓ Preserve streaming response support through litellm — v1.0 (chunk format: `raw_chunk.choices[0].delta.content`)
- ✓ Preserve multi-turn dialogue context through litellm — v1.0
- ✓ Config/env setup for VertexAI (`VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`, `vertex_ai/` model prefix) — v1.0
- ✓ Token counting compatibility — v1.0 (litellm.token_counter() for Gemini; tiktoken cl100k_base fallback for unknown models)
- ✓ RAG pipeline: load → parse → embed → index → retrieve → generate — pre-existing
- ✓ Hybrid retrieval (FAISS semantic + BM25 keyword + graph traversal) — pre-existing
- ✓ Multi-language code parsing via tree-sitter and libcst — pre-existing
- ✓ Iterative agent with confidence-based stopping — pre-existing
- ✓ FastAPI REST API and web UI — pre-existing
- ✓ CLI entry point via Click — pre-existing
- ✓ Configuration via config.yaml and .env — pre-existing
- ✓ Docker + docker-compose deployment — pre-existing
- ✓ Replace `CodeEmbedder` sentence-transformers backend with `litellm.embedding()` calling `vertex_ai/gemini-embedding-001` — v1.1
- ✓ Pass `task_type=RETRIEVAL_DOCUMENT` when indexing, `task_type=RETRIEVAL_QUERY` when embedding queries — v1.1
- ✓ Remove `sentence-transformers` and `torch` from `requirements.txt` and `Dockerfile` — v1.1
- ✓ ADC embedding smoke test (skips in CI, verifies shape/normalization live) — v1.1
- ✓ Migrate `requirements.txt` → `pyproject.toml` with project metadata and dependencies — v1.2
- ✓ Generate and commit `uv.lock` lockfile; builds reproducible across environments — v1.2
- ✓ Separate dev/test deps (`[dependency-groups] dev`) from runtime; excluded via `UV_NO_DEV=1` — v1.2
- ✓ Update `Dockerfile` to install via `uv sync --locked` with two-layer cache pattern — v1.2
- ✓ Remove dead platform import block from `fastcode/__init__.py` — v1.2
- ✓ Make `task_type` explicit at `retriever.py` call sites (lines 415, 734) — v1.2
- ✓ Consolidate `MODEL`/`LITELLM_MODEL` env vars into one (`LITELLM_MODEL` only) — v1.2
- ✓ Verify `_stream_with_summary_filter()` chunk boundary behavior in live multi-turn session — v1.2
- ✓ Replace `rank_bm25` (BM25Okapi, in-memory) with SQLite FTS5 virtual table as the BM25 backend — v1.3 (BM25-01)
- ✓ Persist chunk corpus in a SQLite `chunks` table (replaces pkl serialization) — v1.3 (IDX-01)
- ✓ Trigger-maintained FTS5 index kept in sync with `chunks` on insert/delete/update — v1.3 (STOR-03)
- ✓ `HybridRetriever` BM25 path calls FTS5 instead of `rank_bm25`; FAISS path unchanged — v1.3 (BM25-02)
- ✓ `{repo_name}_bm25.pkl` files no longer written or read; BM25 corpus fully SQLite-backed — v1.3 (BM25-03)
- ✓ Indexer detects unchanged files via content_hash + mtime; skips re-chunking and re-embedding — v1.3 (IDX-02)
- ✓ `embedding_cache` SQLite table stores embeddings keyed on `(content_hash, model)` as BLOB — v1.3 (EMB-01)
- ✓ `CodeEmbedder.embed_text()` checks SQLite cache before calling `litellm.embedding()` — v1.3 (EMB-02)

### Active

<!-- Next milestone requirements go here -->

### Out of Scope

- Nanobot changes — Nanobot already uses litellm via its own provider
- Retrieval strategy changes — FAISS/BM25/graph weights stay as-is
- New retrieval features — no new retrieval strategies, UI changes, etc.
- Multiple simultaneous providers — one active provider at a time is sufficient
- Offline mode — real-time generation is core
- Gemini-native tokenizer in `truncate_to_tokens` — litellm token_counter used for count accuracy
- `src/` layout migration — no structural benefit for this app; editable install achieves same path-independence
- CI workflow (GitHub Actions) — no existing CI; separate milestone concern (PKG-F01)
- Publishing to PyPI — FastCode is an internal tool; installable for local editable install only
- Upstream HKUDS/FastCode sync — separate concern; changes would create significant merge conflicts
- Replace FAISS with sqlite-vec (VEC-01, VEC-02) — FAISS adequate at current scale; deferred to future milestone

## Context

All LLM and embedding calls route through litellm. Package is ~17,000 LOC Python.

**v1.3 shipped 2026-03-02 (Phases 11–14):**
- `fastcode/db.py` created: SQLite schema with `chunks`, `sources`, `chunks_fts` (FTS5 content-linked, trigger-maintained)
- `fastcode/indexer.py`: writes chunks to SQLite with SHA-256 + mtime change detection; unchanged files skipped
- `fastcode/retriever.py`: `full_bm25()` queries FTS5 directly; `rank-bm25` dep and all `.pkl` files eliminated
- `fastcode/embedder.py`: `embed_text()` checks `embedding_cache` SQLite table before calling `litellm.embedding()`; `diskcache` dep removed
- `fastcode/main.py`: `--clear-cache` flag on `index` command truncates `embedding_cache` before indexing
- 42 tests pass; 2 external deps removed (`rank-bm25`, `diskcache`)

**v1.2 shipped 2026-02-27 (Phases 8–10):**
- `pyproject.toml` + `uv.lock` (160 packages, hatchling editable install); `requirements.txt` deleted
- Dockerfile rewritten with uv two-layer cache; `UV_NO_DEV=1` excludes pytest from production image
- Dead `__init__.py` platform block removed; `task_type` explicit at `retriever.py:415` and `:734`
- `MODEL` env var removed; all 5 LLM callers uniformly read `llm_client.DEFAULT_MODEL` (sourced from `LITELLM_MODEL`)

**Install:** `uv sync` (runtime) or `uv sync --no-dev` (production equivalent)

**Known consequences (v1.3 upgrade):**
- Delete `./data/vector_store/` — FAISS indexes incompatible (dimension 384 → 3072, v1.1 change)
- Delete `./data/cache/` — DiskCache no longer read; next index run populates SQLite embedding cache
- `fastcode index --clear-cache` truncates `embedding_cache` (use when switching embedding models)

## Constraints

- **Backward compatibility**: Existing config.yaml patterns still work; `.env` users must rename `MODEL` → `LITELLM_MODEL` (v1.2 breaking change, documented with migration note)
- **Streaming**: `answer_generator.py` streaming preserved via `litellm.completion_stream()` + `choices[0].delta.content` chunk format
- **Docker**: Container deployment works with ADC (mount `~/.config/gcloud` or use workload identity)
- **No new embedding dependencies**: sentence-transformers/torch removed; litellm (already present) handles all embedding calls
- **FAISS index reindex required**: embedding dimension changed (384 → 3072); existing persisted indexes in `./data/vector_store/` must be deleted before first use after v1.1+ upgrade
- **SQLite single-DB convention**: all persistent state (chunks, sources, FTS5 index, embedding cache) lives in one `.db` file at `vector_store.db_path` from config

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Replace direct clients (not wrap) | Cleaner single path, less code to maintain | ✓ Good — 5 files cleanly migrated, zero wrapper complexity |
| Use litellm (not custom abstraction) | Battle-tested, supports 100+ providers, already in Nanobot | ✓ Good — handled provider routing, drop_params, streaming, token counting |
| ADC for auth (not service account JSON) | Simpler credential management, standard GCP pattern | ✓ Good — smoke test confirmed; `gcloud auth application-default login` sufficient |
| `count_tokens(model, text)` reversed signature | Consistent with litellm API; old `utils.count_tokens(text, model)` kept for non-LLM callers | ✓ Good — clean separation; Phase 5 wired all 6 answer_generator call sites |
| Import-time `EnvironmentError` (not at first call) | Fail fast before any LLM call is attempted | ✓ Good — DX improvement; missing vars caught at startup |
| System message in messages list (not `system=` kwarg) | Gemini/VertexAI compatibility — Gemini doesn't accept `system=` parameter | ✓ Good — no model-specific branching needed |
| Delete `llm_utils.py` with callers present | Forces clean migration; `litellm.drop_params=True` supersedes its max_tokens fallback | ✓ Good — no dead stubs; app was intentionally broken until Phase 3/4 |
| `vertex_ai/` prefix in model strings (not `gemini/`) | `gemini/` routes to Google AI Studio, not VertexAI — ADC auth only applies to `vertex_ai/` | ✓ Good — documented in .env.example; prevents silent auth path mismatch |
| Smoke test skips when `VERTEXAI_PROJECT` unset | CI without GCP credentials stays green | ✓ Good — no CI breakage; broad keyword matching avoids litellm version-specific error text |
| ~~`MODEL` and `LITELLM_MODEL` as independent env vars~~ | Pre-v1.2: `answer_generator.py` had its own `MODEL` var; other callers used `LITELLM_MODEL` | ✓ Resolved in v1.2 — `MODEL` removed; all 5 LLM callers now read `llm_client.DEFAULT_MODEL` |
| `litellm.num_retries = 3` global | Transient VertexAI errors auto-retried without per-call config | ✓ Good — set alongside other globals in llm_client.py |
| `litellm.embedding()` with `task_type` kwarg for VertexAI routing | Avoids provider-specific client; same litellm pattern as LLM calls | ✓ Good — R1-R7 all satisfied; smoke test live-confirmed |
| `embedding_dim=3072` read from config at init (no cold-start API call) | FAISS index needs dimension at construction; cold-start call would block init | ✓ Good — CodeEmbedder.__init__() makes zero HTTP calls; dimension hardened via config |
| R8+R10 committed atomically (requirements.txt + main.py default together) | If requirements.txt loses sentence-transformers before main.py is updated, config-absent deploy hits litellm.BadRequestError (not ImportError) | ✓ Good — atomic commit closes the deploy breakage window |
| ~~`embed_text()` default `task_type="RETRIEVAL_QUERY"` — retriever.py callers require zero changes~~ | Backwards-compatible addition; intent was invisible at call site | ✓ Resolved in v1.2 — retriever.py lines 415 and 734 now pass task_type explicitly |
| `pyproject.toml` + hatchling over setuptools | hatchling auto-discovers `fastcode/` at repo root; no `[tool.hatch.build]` config needed | ✓ Good — zero extra config; editable install works out of the box |
| `uv sync --locked` in Dockerfile (not `--frozen`) | `--locked` errors if lockfile is out of date; `--frozen` silently uses whatever is on disk | ✓ Good — stricter reproducibility; catches drift between pyproject.toml and uv.lock |
| PEP 735 `[dependency-groups]` for dev isolation | Alternative to `[project.optional-dependencies]`; uv-native; excludable with `UV_NO_DEV=1` | ✓ Good — clean separation; production image verified pytest-free |
| Remove `MODEL` env var entirely (not alias/deprecate) | Aliasing preserves the confusion; clean break with migration note is clearer | ✓ Good — `.env.example` migration note documents the change for upgraders |
| FTS5 content-linked table (content=chunks) over contentless | Retriever can read chunk text from FTS without extra JOIN | ✓ Good — Phase 11; simplifies full_bm25() query |
| WAL mode omitted from SQLite init | Single-process CLI tool; no concurrent readers | ✓ Good — Phase 11; keeps schema simple |
| `executescript()` for all DDL | Cleaner single call vs N individual execute() calls | ✓ Good — Phase 11; idempotent via CREATE IF NOT EXISTS |
| mtime_ns fast-path before SHA-256 hash in indexer | Avoids hashing unchanged files on repeated indexing runs | ✓ Good — Phase 12; significant speedup for large repos |
| Per-file SQLite transaction with DELETE+INSERT (cascade clears chunks) | Atomic replacement; no orphan chunk rows | ✓ Good — Phase 12 |
| `full_bm25()` as method not attribute; removed `self.full_bm25` BM25Okapi attr | Avoids name collision between method and old instance attribute | ✓ Good — Phase 13 (P01); auto-fixed BM25Okapi assignments in index_for_bm25/load_bm25 |
| `score=1.0` placeholder in `_keyword_search()` | FTS5 rank used for ordering; normalized float score not needed | ✓ Good — Phase 13 (P01); ordering correctness preserved via ORDER BY fts.rank |
| `_simple_bm25_scores` TF sum for repo overview (not BM25Okapi) | Corpus is <20 repos; IDF component irrelevant at this scale; removes external dep | ✓ Good — Phase 13 (P02); rank-bm25 removed from pyproject.toml |
| `repo_overview_bm25 = True` sentinel after build | Existing `is not None` guard treats True as truthy; no conditional code change needed | ✓ Good — Phase 13 (P02); clean drop-in replacement |
| BLOB (float32 bytes) for embedding storage, not JSON | 4× smaller than JSON; numpy frombuffer roundtrip is microseconds | ✓ Good — Phase 14 (P01); matches schema spec |
| Validate embedding shape on cache retrieval, raise ValueError | Surfacing model-switch misconfiguration is better than silently returning wrong-dim vectors | ✓ Good — Phase 14 (P01); error message includes --clear-cache hint |
| `embed_text()` signature unchanged — cache transparent to callers | Zero changes to indexer or retriever call sites | ✓ Good — Phase 14 (P01); drop-in replacement for DiskCache |
| `--clear-cache` on `index` command (not standalone command) | Primary use case is clearing before re-indexing; separate command adds scope | ✓ Good — Phase 14 (P02) |
| Start fresh on DiskCache → SQLite migration (no data migration) | DiskCache format incompatible; cache is performance optimization only | ✓ Good — Phase 14 (P02); clean break |

---
*Last updated: 2026-03-02 after v1.3 milestone*
