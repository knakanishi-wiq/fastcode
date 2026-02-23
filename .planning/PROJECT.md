# FastCode — LiteLLM Provider Migration

## What This Is

FastCode is a code intelligence backend (RAG pipeline + agentic retrieval) that currently uses direct `openai` and `anthropic` Python clients for all LLM calls. This project replaces those direct clients with litellm, enabling VertexAI as the LLM provider through existing GCP infrastructure. The change touches all LLM call sites: answer generation, query processing, query rewriting, and the iterative agent.

## Core Value

All LLM calls in FastCode route through litellm, so the system works with VertexAI on GCP without maintaining separate provider-specific client code.

## Requirements

### Validated

- ✓ RAG pipeline: load → parse → embed → index → retrieve → generate — existing
- ✓ Hybrid retrieval (FAISS semantic + BM25 keyword + graph traversal) — existing
- ✓ Multi-language code parsing via tree-sitter and libcst — existing
- ✓ Iterative agent with confidence-based stopping — existing
- ✓ FastAPI REST API and web UI — existing
- ✓ CLI entry point via Click — existing
- ✓ Configuration via config.yaml and .env — existing
- ✓ Docker + docker-compose deployment — existing

### Active

- [ ] Replace direct openai/anthropic clients with litellm across all LLM call sites
- [ ] VertexAI support via litellm with ADC authentication
- [ ] Preserve streaming response support through litellm
- [ ] Preserve multi-turn dialogue context through litellm
- [ ] Config/env setup for VertexAI (project ID, location, model name)
- [ ] Token counting compatibility (currently uses tiktoken)

### Out of Scope

- Nanobot changes — Nanobot already uses litellm via its own provider
- Embedding model changes — sentence-transformers stays as-is (not an LLM call)
- New features beyond provider swap — no new retrieval strategies, UI changes, etc.
- Multiple simultaneous providers — one active provider at a time is sufficient

## Context

- FastCode's LLM calls are spread across 4 files: `answer_generator.py`, `llm_utils.py`, `query_processor.py`, `iterative_agent.py`
- The `openai` client is used in OpenAI-compatible mode (also supports custom `BASE_URL` for OpenRouter/Ollama)
- Nanobot already demonstrates litellm usage in `nanobot/nanobot/providers/litellm_provider.py` — can reference patterns
- VertexAI authentication will use Application Default Credentials (ADC) — `gcloud auth application-default login` locally, default service account in GCP
- litellm handles VertexAI auth via ADC natively when model is prefixed with `vertex_ai/`

## Constraints

- **Backward compatibility**: Existing config.yaml and .env patterns should still work (just different env vars)
- **Streaming**: answer_generator.py supports streaming responses — litellm must preserve this
- **Docker**: Container deployment must work with ADC (mount credentials or use workload identity)
- **No new embedding dependencies**: Only LLM text generation calls are migrated

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Replace direct clients (not wrap) | Cleaner single path, less code to maintain | — Pending |
| Use litellm (not custom abstraction) | Battle-tested, supports 100+ providers, already used in Nanobot | — Pending |
| ADC for auth (not service account JSON) | Simpler credential management, standard GCP pattern | — Pending |

---
*Last updated: 2026-02-24 after initialization*
