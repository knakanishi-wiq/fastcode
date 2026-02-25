# Roadmap: FastCode — LiteLLM Provider Migration

## Overview

This migration replaces direct openai/anthropic Python clients with litellm across all LLM call sites in FastCode, enabling VertexAI as the primary provider via GCP Application Default Credentials. The work proceeds in dependency order: validate the VertexAI connection first, create the centralized client module, migrate the four lower-risk non-streaming files, then tackle the highest-risk streaming path in answer_generator.py while cleaning up vestigial config.

## Phases

- [x] **Phase 1: Config and Dependencies** - Install litellm, configure VertexAI env vars, validate ADC connection
- [x] **Phase 2: Core Infrastructure** - Create llm_client.py, fix token counting, delete llm_utils.py (completed 2026-02-24)
- [x] **Phase 3: Non-Streaming Migration** - Migrate query_processor, iterative_agent, repo_overview, repo_selector to llm_client (completed 2026-02-24)
- [ ] **Phase 4: Streaming Migration and Finalization** - Migrate answer_generator.py streaming path, clean up config

## Phase Details

### Phase 1: Config and Dependencies
**Goal**: VertexAI connection is validated and working before any FastCode code is changed
**Depends on**: Nothing (first phase)
**Requirements**: CONF-01, CONF-02, CONF-04
**Success Criteria** (what must be TRUE):
  1. `litellm[google]` is installed and importable with no dependency conflicts
  2. A standalone Python script calling `litellm.completion("vertex_ai/gemini-2.0-flash-001", ...)` returns a valid response using ADC credentials
  3. `.env.example` documents all required VertexAI vars (`VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`, model name format)
  4. Running the smoke test without `VERTEXAI_PROJECT` set produces a clear configuration error, not a misleading 401
**Plans**: 1 plan

Plans:
- [x] 01-01-PLAN.md — Install litellm[google], configure .env.example with VertexAI vars, create smoke test

### Phase 2: Core Infrastructure
**Goal**: Centralized llm_client.py module exists and token counting works correctly for VertexAI model names
**Depends on**: Phase 1
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, TOKN-01
**Success Criteria** (what must be TRUE):
  1. `fastcode/llm_client.py` exports `completion()` and `completion_stream()` callable from any FastCode module
  2. `litellm.drop_params = True` and `litellm.suppress_debug_info = True` are set once at startup, not per-call
  3. `count_tokens("vertex_ai/gemini-2.0-flash-001", text)` returns a numeric value without raising KeyError
  4. `fastcode/llm_utils.py` no longer exists in the codebase
**Plans**: 2 plans

Plans:
- [ ] 02-01-PLAN.md — Create fastcode/llm_client.py with TDD (completion, completion_stream, count_tokens, env validation)
- [ ] 02-02-PLAN.md — Delete fastcode/llm_utils.py (superseded by litellm.drop_params=True)

### Phase 3: Non-Streaming Migration
**Goal**: All non-streaming LLM call sites use llm_client instead of direct provider clients
**Depends on**: Phase 2
**Requirements**: MIGR-01, MIGR-02, MIGR-03, MIGR-04, MIGR-05
**Success Criteria** (what must be TRUE):
  1. `query_processor.py`, `iterative_agent.py`, `repo_overview.py`, and `repo_selector.py` contain no imports of `openai` or `anthropic`
  2. Provider dispatch branches (`if provider == "openai"`) are absent from all four migrated files
  3. Sending a query through the API returns a valid code answer routed via VertexAI
  4. The iterative agent completes a multi-turn retrieval cycle without system message errors from Gemini
**Plans**: 4 plans

Plans:
- [ ] 03-01-PLAN.md — Migrate query_processor.py to llm_client (MIGR-01, MIGR-05)
- [ ] 03-02-PLAN.md — Migrate repo_selector.py to llm_client (MIGR-04, MIGR-05)
- [ ] 03-03-PLAN.md — Migrate repo_overview.py to llm_client (MIGR-03, MIGR-05)
- [ ] 03-04-PLAN.md — Migrate iterative_agent.py to llm_client + requirements.txt cleanup (MIGR-02, MIGR-05)

### Phase 4: Streaming Migration and Finalization
**Goal**: answer_generator.py streaming works through litellm and all provider-specific config is removed
**Depends on**: Phase 3
**Requirements**: STRM-01, STRM-02, STRM-03, CONF-03
**Success Criteria** (what must be TRUE):
  1. A streaming query via the web UI receives token-by-token chunks without errors or silent truncation
  2. Responses containing `<SUMMARY>` tags are correctly buffered and filtered by `_stream_with_summary_filter()` using litellm chunk format
  3. `answer_generator.py` contains no `_generate_openai_*` or `_generate_anthropic_*` methods
  4. `config/config.yaml` contains no `generation.provider` field or `openai`/`anthropic` sections
**Plans**: 2 plans

Plans:
- [ ] 04-01-PLAN.md — Migrate answer_generator.py to llm_client (STRM-01, STRM-02, STRM-03)
- [ ] 04-02-PLAN.md — Clean config.yaml and .env.example of provider-specific fields (CONF-03)

### Phase 5: Fix answer_generator.py Wiring and Cleanup
**Goal:** All partial requirements from the v1.0 audit are fully satisfied — answer_generator.py routes token counting through llm_client, MODEL env var has a safe fallback, dead dependencies are removed, and .env.example documents all required vars
**Depends on**: Phase 4
**Requirements**: TOKN-01, STRM-01, STRM-02, STRM-03, CONF-01, CONF-02
**Gap Closure:** Closes gaps from v1.0 audit
**Success Criteria** (what must be TRUE):
  1. `answer_generator.py` imports `count_tokens` from `fastcode.llm_client`, not `fastcode.utils`
  2. All `count_tokens` call sites use reversed arg order `(self.model, prompt)` matching `llm_client.count_tokens` signature
  3. `self.model` falls back to `llm_client.DEFAULT_MODEL` when `MODEL` env var is unset
  4. `requirements.txt` contains no `openai` or `anthropic` entries
  5. `.env.example` documents `LITELLM_MODEL` and includes a `vertex_ai/` prefix hint for `MODEL`
**Plans**: 1 plan

Plans:
- [ ] 05-01-PLAN.md — Fix answer_generator.py wiring, clean requirements.txt, update .env.example

## Progress

**Execution Order:** 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Config and Dependencies | 1/1 | Complete | 2026-02-24 |
| 2. Core Infrastructure | 2/2 | Complete   | 2026-02-24 |
| 3. Non-Streaming Migration | 4/4 | Complete   | 2026-02-24 |
| 4. Streaming Migration and Finalization | 1/2 | In Progress|  |
| 5. Fix answer_generator.py Wiring and Cleanup | 0/1 | Pending | |
