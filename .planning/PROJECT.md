# FastCode — LiteLLM Provider Migration

## What This Is

FastCode is a code intelligence backend (RAG pipeline + agentic retrieval) that routes all LLM calls through litellm, enabling VertexAI on GCP via Application Default Credentials. The v1.0 migration replaced direct openai/anthropic Python clients across all five LLM call sites (`answer_generator.py`, `query_processor.py`, `iterative_agent.py`, `repo_overview.py`, `repo_selector.py`) with a centralized `fastcode/llm_client.py` module.

## Core Value

All LLM calls in FastCode route through litellm, so the system works with VertexAI on GCP without maintaining separate provider-specific client code.

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

### Active

*(Define with `/gsd:new-milestone` for next milestone)*

### Out of Scope

- Nanobot changes — Nanobot already uses litellm via its own provider
- Embedding model changes — sentence-transformers stays as-is (not an LLM call)
- New features beyond provider swap — no new retrieval strategies, UI changes, etc.
- Multiple simultaneous providers — one active provider at a time is sufficient
- Offline mode — real-time generation is core
- Gemini-native tokenizer in `truncate_to_tokens` — litellm token_counter used for count accuracy; tiktoken cl100k_base used for encode/decode truncation (close enough for context window management)

## Context

FastCode's LLM calls route through `fastcode/llm_client.py`. Package is ~16,600 LOC Python (13 source files). All 5 call sites migrated. Streaming tested live against VertexAI (`gemini-3-flash-preview`) — 13/13 smoke tests passing.

**Remaining tech debt (environmental):**
- Streaming UI token-by-token observation (requires live browser session)
- `_stream_with_summary_filter()` SUMMARY tag chunk boundary behavior (requires live multi-turn session)

## Constraints

- **Backward compatibility**: Existing config.yaml and .env patterns still work — only env var names changed (`MODEL`, `LITELLM_MODEL` instead of OpenAI API key)
- **Streaming**: `answer_generator.py` streaming preserved via `litellm.completion_stream()` + `choices[0].delta.content` chunk format
- **Docker**: Container deployment works with ADC (mount `~/.config/gcloud` or use workload identity)
- **No new embedding dependencies**: Only LLM text generation calls migrated

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

---
*Last updated: 2026-02-25 after v1.0 milestone*
