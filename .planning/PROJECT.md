# FastCode — LiteLLM Provider Migration

## What This Is

FastCode is a code intelligence backend (RAG pipeline + agentic retrieval) that routes all LLM and embedding calls through litellm, enabling VertexAI on GCP via Application Default Credentials. v1.0 migrated all five LLM call sites to a centralized `fastcode/llm_client.py`. v1.1 completed the GCP-native story by replacing the local sentence-transformers embedding backend with VertexAI `gemini-embedding-001` via litellm — eliminating torch/sentence-transformers from the dependency tree entirely.

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

### Active

<!-- v1.2 uv Migration & Tech Debt Cleanup -->

- [ ] Migrate `requirements.txt` → `pyproject.toml` with project metadata and dependencies
- [ ] Generate `uv.lock` lockfile
- [ ] Separate dev/test extras from runtime dependencies
- [ ] Update `Dockerfile` to install via `uv` instead of `pip`
- [ ] Remove dead platform import block from `fastcode/__init__.py`
- [ ] Make `task_type` explicit at `retriever.py` call sites (lines 415, 734)
- [ ] Consolidate `MODEL` and `LITELLM_MODEL` env vars into one
- [ ] Test `_stream_with_summary_filter()` chunk boundary behavior in live multi-turn session

### Out of Scope

- Nanobot changes — Nanobot already uses litellm via its own provider
- Retrieval strategy changes — FAISS/BM25/graph weights stay as-is; only the embedding backend changes
- New retrieval features — no new retrieval strategies, UI changes, etc.
- Multiple simultaneous providers — one active provider at a time is sufficient
- Offline mode — real-time generation is core
- Gemini-native tokenizer in `truncate_to_tokens` — litellm token_counter used for count accuracy; tiktoken cl100k_base used for encode/decode truncation (close enough for context window management)

## Context

All LLM and embedding calls route through litellm. Package is ~55,300 LOC Python. v1.1 shipped 2026-02-25 — both phases complete, 11/11 requirements satisfied, smoke test passed live against VertexAI ADC.

**Shipped v1.1 (Phases 6–7):** `fastcode/embedder.py` rewritten, `sentence-transformers`/`torch` removed from all dependency manifests, `tests/test_embedder_smoke.py` live-verified (shape `(3072,)`, L2 norm 1.0, `gemini-embedding-001`).

**Remaining tech debt (v1.1):**
- `fastcode/__init__.py` platform import block — dead code post sentence-transformers removal; tracked in `deferred-items.md`
- `retriever.py` lines 415, 734 rely on `embed_text()` default `task_type` — correct at runtime, but intent invisible at call site
- Streaming UI token-by-token observation (requires live browser session)
- `_stream_with_summary_filter()` SUMMARY tag chunk boundary behavior (requires live multi-turn session)

**Known consequence:** Existing FAISS indexes are incompatible (dimension 384 → 3072); delete `./data/vector_store/` before first use after upgrade.

## Constraints

- **Backward compatibility**: Existing config.yaml and .env patterns still work — only env var names changed (`MODEL`, `LITELLM_MODEL` instead of OpenAI API key)
- **Streaming**: `answer_generator.py` streaming preserved via `litellm.completion_stream()` + `choices[0].delta.content` chunk format
- **Docker**: Container deployment works with ADC (mount `~/.config/gcloud` or use workload identity)
- **No new embedding dependencies**: sentence-transformers/torch removed; litellm (already present) handles all embedding calls
- **FAISS index reindex required**: embedding dimension changed (384 → 3072); existing persisted indexes in `./data/vector_store/` must be deleted before first use after upgrade

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
| `MODEL` and `LITELLM_MODEL` as independent env vars | `answer_generator.py` has pre-existing `MODEL` var; other callers use `LITELLM_MODEL` via DEFAULT_MODEL | ⚠ Revisit — operational confusion risk; documented in .env.example but independence not obvious |
| `litellm.num_retries = 3` global | Transient VertexAI errors auto-retried without per-call config | ✓ Good — set alongside other globals in llm_client.py |
| `litellm.embedding()` with `task_type` kwarg for VertexAI routing | Avoids provider-specific client; same litellm pattern as LLM calls | ✓ Good — R1-R7 all satisfied; smoke test live-confirmed |
| `embedding_dim=3072` read from config at init (no cold-start API call) | FAISS index needs dimension at construction; cold-start call would block init | ✓ Good — CodeEmbedder.__init__() makes zero HTTP calls; dimension hardened via config |
| R8+R10 committed atomically (requirements.txt + main.py default together) | If requirements.txt loses sentence-transformers before main.py is updated, config-absent deploy hits litellm.BadRequestError (not ImportError) | ✓ Good — atomic commit closes the deploy breakage window |
| `embed_text()` default `task_type="RETRIEVAL_QUERY"` — retriever.py callers require zero changes | Backwards-compatible addition; intent is visible in embedder.py signature | ⚠ Revisit — retriever.py call sites (lines 415, 734) don't forward task_type explicitly; latent fragility if default changes |
| `ENV TOKENIZERS_PARALLELISM=false` left in Dockerfile | Harmless no-op after sentence-transformers removal; R9 spec excluded it | ✓ Good — no harm; can be removed in a future cleanup |

## Current Milestone: v1.2 uv Migration & Tech Debt Cleanup

**Goal:** Modernize packaging with uv (pyproject.toml + lockfile + Dockerfile) and close the four open tech debt items from v1.1.

**Target features:**
- Full uv migration (pyproject.toml, uv.lock, Dockerfile, dev/test extras)
- Remove dead `__init__.py` platform import block
- Explicit `task_type` at `retriever.py` call sites
- Consolidate `MODEL`/`LITELLM_MODEL` env vars into one
- Streaming smoke test for `_stream_with_summary_filter()`

---
*Last updated: 2026-02-26 after v1.2 milestone started*
