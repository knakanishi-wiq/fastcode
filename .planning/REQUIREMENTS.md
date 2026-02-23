# Requirements: FastCode — LiteLLM Provider Migration

**Defined:** 2026-02-24
**Core Value:** All LLM calls in FastCode route through litellm, enabling VertexAI on GCP without provider-specific client code.

## v1 Requirements

### LLM Client Infrastructure

- [ ] **INFRA-01**: Centralized `fastcode/llm_client.py` module exposes `completion()` and `completion_stream()` via litellm
- [ ] **INFRA-02**: litellm globals set at startup: `drop_params=True`, `suppress_debug_info=True`
- [ ] **INFRA-03**: `llm_utils.py` deleted — its functionality replaced by litellm param handling
- [ ] **INFRA-04**: Fallback/retry configuration via litellm's built-in retry logic

### Non-Streaming Migration

- [ ] **MIGR-01**: `query_processor.py` uses litellm via `llm_client` instead of direct openai/anthropic calls
- [ ] **MIGR-02**: `iterative_agent.py` uses litellm via `llm_client` instead of direct openai/anthropic calls
- [ ] **MIGR-03**: `repo_overview.py` uses litellm via `llm_client` instead of direct openai/anthropic calls
- [ ] **MIGR-04**: `repo_selector.py` uses litellm via `llm_client` instead of direct openai/anthropic calls
- [ ] **MIGR-05**: Provider dispatch logic (`if provider == "openai"` branches) removed from all migrated files

### Streaming Migration

- [ ] **STRM-01**: `answer_generator.py` non-streaming `generate()` uses litellm via `llm_client`
- [ ] **STRM-02**: `answer_generator.py` streaming `generate_stream()` uses litellm via `llm_client`
- [ ] **STRM-03**: `_stream_with_summary_filter()` works correctly with litellm chunk format

### Configuration & Auth

- [x] **CONF-01**: `requirements.txt` includes `litellm[google]` with version pin
- [x] **CONF-02**: `.env.example` documents VertexAI vars: `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`, model name format
- [ ] **CONF-03**: `config.yaml` cleaned of provider-specific sections (no more `openai`/`anthropic` branches)
- [x] **CONF-04**: VertexAI works with ADC authentication (`gcloud auth application-default login`)

### Token Counting

- [ ] **TOKN-01**: `count_tokens()` in `utils.py` uses `litellm.token_counter()` instead of direct tiktoken

## v2 Requirements

### Observability

- **OBSV-01**: Request logging via litellm callbacks
- **OBSV-02**: Cost tracking per query via litellm's cost calculation

### Docker

- **DOCK-01**: Docker ADC credential mounting documented
- **DOCK-02**: Docker Compose updated for VertexAI environment variables

## Out of Scope

| Feature | Reason |
|---------|--------|
| Nanobot migration | Already uses litellm via its own provider |
| Embedding model changes | sentence-transformers is not an LLM call |
| Multiple simultaneous providers | One active provider at a time is sufficient |
| New retrieval strategies | Provider swap only, no feature additions |
| OAuth/service account JSON auth | ADC is the chosen auth method |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONF-01 | Phase 1 | Complete |
| CONF-02 | Phase 1 | Complete |
| CONF-04 | Phase 1 | Complete |
| INFRA-01 | Phase 2 | Pending |
| INFRA-02 | Phase 2 | Pending |
| INFRA-03 | Phase 2 | Pending |
| INFRA-04 | Phase 2 | Pending |
| TOKN-01 | Phase 2 | Pending |
| MIGR-01 | Phase 3 | Pending |
| MIGR-02 | Phase 3 | Pending |
| MIGR-03 | Phase 3 | Pending |
| MIGR-04 | Phase 3 | Pending |
| MIGR-05 | Phase 3 | Pending |
| STRM-01 | Phase 4 | Pending |
| STRM-02 | Phase 4 | Pending |
| STRM-03 | Phase 4 | Pending |
| CONF-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-24*
*Last updated: 2026-02-24 after roadmap creation*
