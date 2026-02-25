# Project Research Summary

**Project:** FastCode — LiteLLM + VertexAI Provider Migration
**Domain:** LLM provider abstraction layer migration (direct openai/anthropic clients → litellm + VertexAI)
**Researched:** 2026-02-24
**Confidence:** HIGH

## Executive Summary

FastCode is a Python code intelligence backend that currently makes direct LLM API calls to OpenAI and Anthropic via their vendor-specific SDKs. The migration replaces those SDKs with litellm as a unified abstraction layer, enabling VertexAI (Gemini) as the primary provider via GCP Application Default Credentials. litellm is already proven in this codebase via Nanobot (`litellm>=1.0.0`), the migration path is well-documented, and the API shape is nearly identical to the existing OpenAI streaming pattern — making this a primarily mechanical substitution with a small number of critical edge cases to handle carefully.

The recommended approach is to create a new `fastcode/llm_client.py` module as the single point of litellm configuration and invocation, then migrate the five LLM-calling files one at a time in risk order (non-streaming first, `answer_generator.py` last). The `vertex_ai/` model name prefix, `VERTEXAI_PROJECT` and `VERTEXAI_LOCATION` env vars, and `litellm.drop_params = True` are the minimum viable configuration requirements. Token counting must be migrated from tiktoken to `litellm.token_counter()` before integration testing, because tiktoken silently produces incorrect counts for VertexAI model names.

The key risks are: (1) streaming path breakage in `answer_generator.py` — the Anthropic stream context manager pattern does not exist in litellm and must be replaced with the OpenAI-compatible chunk iterator; (2) silent ADC auth failure in Docker when credentials are not mounted; (3) system message handling differences for Gemini models in `iterative_agent.py`. All three risks are well-understood and preventable with targeted testing.

## Key Findings

### Recommended Stack

litellm (`>=1.61.0`, latest 1.81.14) is the single new dependency, installed with the `google` extra (`litellm[google]>=1.61.0`) which pulls in `google-cloud-aiplatform>=1.38.0` for VertexAI support. No new auth dependency is needed — `google-auth` arrives transitively and provides ADC. The `openai` and `anthropic` packages are removed as direct dependencies, though `openai` remains as a litellm transitive dependency. tiktoken stays in `requirements.txt` as a fallback for the token counter migration.

**Core technologies:**
- `litellm[google]>=1.61.0`: Unified LLM client replacing direct openai/anthropic SDKs — battle-tested, already in Nanobot, zero-config VertexAI via `vertex_ai/` prefix
- `google-cloud-aiplatform>=1.38.0`: Required VertexAI client (installed automatically via litellm google extra) — current latest 1.138.0 satisfies the `>=1.38.0` floor
- `tiktoken>=0.7.0`: Keep as fallback for token counting until litellm path is verified — `cl100k_base` gives approximate but acceptable counts for Gemini
- GCP ADC (no new package): litellm calls `google.auth.default()` automatically for `vertex_ai/` models when `VERTEXAI_CREDENTIALS` is unset — zero code required

### Expected Features

All features in scope are table stakes for migration correctness. There are no "nice to have" features in this migration — every item either is required or is explicitly deferred.

**Must have (table stakes):**
- `litellm.completion()` sync and `stream=True` — replaces all 4 provider-specific call paths across 5 files
- `vertex_ai/` model prefix routing — enables VertexAI without any code changes at call sites (only env var change)
- ADC authentication via `VERTEXAI_PROJECT` + `VERTEXAI_LOCATION` env vars — no secrets in code
- `litellm.drop_params = True` at startup — prevents 400 errors on models that reject unknown parameters (e.g., reasoning models rejecting `temperature`)
- `litellm.suppress_debug_info = True` at startup — prevents credential leakage in logs
- Token counting fix in `fastcode/utils.py` — replace tiktoken with `litellm.token_counter()` to avoid silent wrong counts for VertexAI model names
- OpenAI-compatible response object access (`response.choices[0].message.content`) — preserved by litellm's normalization

**Should have (operational quality):**
- Startup env var validation with clear error messages before first LLM call — prevents misleading 401 errors from missing `VERTEXAI_PROJECT`
- ADC credential mount in `docker-compose.yml` for local dev — prevents silent failures at query time
- Smoke test call at container startup — validates auth before service is marked healthy

**Defer (v2+):**
- `litellm.acompletion()` async: Requires FastCode sync-to-async refactor — separate milestone
- `litellm.success_callback` / observability hooks: Useful for GCP cost tracking, not needed for functional migration
- Budget tracking via `litellm.max_budget`: Operational concern, post-migration
- Provider fallback/retry config (`fallbacks=[...]`): Reduces fragility but not required for migration

### Architecture Approach

The recommended pattern is a single `fastcode/llm_client.py` module that acts as the sole point of litellm configuration and invocation. All five LLM-calling files (`answer_generator.py`, `query_processor.py`, `iterative_agent.py`, `repo_selector.py`, `repo_overview.py`) import `completion` and `completion_stream` from this module rather than initializing their own provider clients. This eliminates the current 5x-duplicated `_initialize_client()` pattern, centralizes litellm global state (`drop_params`, `suppress_debug_info`, env var validation), and makes the provider a module-level concern driven entirely by the `MODEL` env var prefix.

**Major components:**
1. `fastcode/llm_client.py` (NEW) — Single litellm wrapper with `configure_litellm()`, `completion()`, and `completion_stream()`. Called once at startup by `FastCode.__init__()`. Reads `MODEL`, `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION` from env.
2. `fastcode/answer_generator.py` (MODIFIED, highest risk) — Remove 4 provider-specific generate methods and `_initialize_client()`; replace with calls to `llm_client.completion()` and `llm_client.completion_stream()`. The `_stream_with_summary_filter()` buffering logic is provider-agnostic and unchanged.
3. `fastcode/query_processor.py`, `fastcode/iterative_agent.py`, `fastcode/repo_selector.py`, `fastcode/repo_overview.py` (MODIFIED, lower risk) — Remove client init and `_call_openai`/`_call_anthropic` dispatch; replace with single `llm_client.completion()` call.
4. `fastcode/llm_utils.py` (DELETE) — The `openai_chat_completion()` wrapper is made redundant by `litellm.drop_params = True`.
5. `fastcode/utils.py` (MODIFY) — Replace `tiktoken.encoding_for_model()` in `count_tokens()` with `litellm.token_counter()` plus `try/except` fallback to `cl100k_base`.
6. `config/config.yaml` (MODIFY) — Remove `generation.provider` field; provider is now encoded in the `MODEL` env var prefix.

### Critical Pitfalls

1. **tiktoken silently wrong for VertexAI model names** — `tiktoken.encoding_for_model("vertex_ai/gemini-2.0-flash-001")` raises `KeyError` and falls back to `cl100k_base`, undercounting or overcounting tokens by 15–40%. This corrupts the context budget guard before every LLM call. Replace `count_tokens()` with `litellm.token_counter()` before any integration testing.

2. **Anthropic streaming path is incompatible with litellm** — The existing `_generate_anthropic_stream()` uses `messages.stream()` context manager and `stream.text_stream` iteration. litellm does not expose this pattern. Must be replaced with `for chunk in litellm.completion(..., stream=True): chunk.choices[0].delta.content`. Test streaming end-to-end before marking migration complete.

3. **ADC credentials not mounted in Docker — silent failure at query time** — `google.auth.exceptions.DefaultCredentialsError` is raised at the first LLM call, not at startup. Container starts cleanly, first user query fails. Mount `~/.config/gcloud` as a volume in `docker-compose.yml` and add a startup health check LLM call.

4. **Missing `VERTEXAI_PROJECT`/`VERTEXAI_LOCATION` produces misleading 401 errors** — The VertexAI API returns auth errors rather than config errors when the project is missing. Add startup validation that checks for these env vars and raises a clear `ConfigurationError` before the first call.

5. **Gemini rejects `role: system` messages — iterative agent specific** — `iterative_agent.py` passes a system message as the first messages array entry. Some Gemini models reject `role: system`; litellm performs the `system` → `system_instruction` conversion but this is version-dependent. Test the iterative agent path separately from answer generation.

## Implications for Roadmap

Based on research, the migration has a clear dependency order that dictates phase structure. Configuration and environment must be validated before code migration begins; token counting must be fixed before integration testing; non-streaming callers should be migrated before the streaming path.

### Phase 1: Foundation — Dependency and Config Setup

**Rationale:** The VertexAI env vars and litellm installation must work before any code changes. Pitfall 10 (misleading 401 errors from missing project config) and Pitfall 4 (Docker ADC) are best caught here with a standalone smoke test — not discovered mid-code migration.

**Delivers:** Working litellm + VertexAI connection validated independently of FastCode code; `requirements.txt` updated; `.env.example` documented; Docker credential mount confirmed.

**Addresses:** Table stakes — VertexAI auth, `vertex_ai/` prefix routing, `VERTEXAI_PROJECT` + `VERTEXAI_LOCATION` env vars

**Avoids:** Pitfall 10 (missing env vars → misleading 401), Pitfall 4 (Docker ADC silent failure), Pitfall 2 (wrong model name format)

### Phase 2: Core Infrastructure — Create `llm_client.py` and Fix Token Counting

**Rationale:** `fastcode/llm_client.py` is a pure addition (no risk to existing code) and provides the stable foundation all subsequent file migrations depend on. Token counting must be fixed before integration testing — if done later, tests against VertexAI produce incorrect context budget decisions.

**Delivers:** `fastcode/llm_client.py` with `configure_litellm()`, `completion()`, `completion_stream()`; `fastcode/utils.py` `count_tokens()` migrated to `litellm.token_counter()`; `fastcode/llm_utils.py` marked for deletion.

**Uses:** litellm sync API, `litellm.drop_params = True`, `litellm.suppress_debug_info = True`, `litellm.token_counter()`

**Implements:** Centralized LiteLLM client architecture pattern

**Avoids:** Pitfall 1 (tiktoken wrong counts), Pitfall 9 (temperature rejected), Pitfall 11 (verbose logging/credential leakage)

### Phase 3: Non-Streaming Migration — Four Lower-Risk Files

**Rationale:** `repo_overview.py`, `repo_selector.py`, `query_processor.py`, and `iterative_agent.py` are all non-streaming single-call patterns. Migrating them first builds confidence with lower-risk changes before touching the streaming path.

**Delivers:** Four files fully migrated to `llm_client.completion()`; `llm_utils.py` deleted; provider dispatch branches removed; per-file client init removed.

**Addresses:** All non-streaming table stakes call sites

**Avoids:** Pitfall 6 (llm_utils wrong exception type), Pitfall 7 (duplicate client init), Anti-Pattern 2 (preserving provider dispatch)

**Note:** Test `iterative_agent.py` specifically for Pitfall 5 (system message Gemini compatibility).

### Phase 4: Streaming Migration — `answer_generator.py`

**Rationale:** Highest-risk file, migrated last after all patterns are validated. Contains both streaming and non-streaming paths, plus the `_stream_with_summary_filter()` buffering logic that must continue to receive correctly-shaped chunks.

**Delivers:** `answer_generator.py` fully migrated; all four `_generate_*` methods removed; streaming protocol (`yield (chunk, None)` / `yield (None, metadata)`) preserved unchanged for `web_app.py` and `api.py` consumers.

**Uses:** `litellm.completion(stream=True)` with `chunk.choices[0].delta.content` iteration

**Implements:** Architecture Pattern 3 (keep streaming contract unchanged)

**Avoids:** Pitfall 3 (Anthropic stream context manager incompatible with litellm), Pitfall 12 (response object access), Pitfall 13 (multi-turn dialogue role normalization)

### Phase 5: Cleanup and Config Finalization

**Rationale:** After all call sites are migrated and tested end-to-end, remove vestigial configuration and validate the complete system.

**Delivers:** `config/config.yaml` `generation.provider` field removed; `.env.example` finalized; any remaining `openai`/`anthropic` imports removed; end-to-end integration test across all providers (VertexAI, OpenAI, Anthropic) confirmed working.

**Addresses:** Anti-features — dual code paths, BASE_URL for VertexAI, orphaned config fields

### Phase Ordering Rationale

- Phase 1 must precede all others: VertexAI config errors produce misleading failures that would be hard to distinguish from code bugs during migration
- Phase 2 infrastructure must precede Phase 3/4: All migrated files depend on `llm_client.py`; token counting must be correct before any VertexAI calls
- Phase 3 (non-streaming) precedes Phase 4 (streaming): Validates the litellm completion API and response object shape before adding streaming complexity
- Phase 4 is isolated last: The streaming path in `answer_generator.py` is the only file with the incompatible Anthropic pattern and carries the highest regression risk
- Phase 5 is cosmetic cleanup: No functional risk, deferred to avoid blocking the core migration

### Research Flags

Phases with well-documented patterns (standard implementation, skip deeper research):
- **Phase 1:** litellm VertexAI config is fully documented in verified source; ADC mount patterns are standard GCP
- **Phase 2:** `llm_client.py` pattern is proven by Nanobot reference implementation in the same repo; `litellm.token_counter()` API is stable
- **Phase 3:** Non-streaming call replacement is mechanical; all patterns verified against Nanobot
- **Phase 5:** Config cleanup is deterministic given prior phases

Phases that may warrant targeted verification before implementation:
- **Phase 4:** Streaming migration — the `_stream_with_summary_filter()` summary tag buffer logic (120+ lines) may behave differently with litellm chunk sizes vs Anthropic chunk sizes. Recommend reading that method in full before implementing and testing with long responses that contain `<SUMMARY>` tags.
- **Phase 3 (iterative agent):** System message conversion for Gemini is version-dependent in litellm. Verify behavior against the pinned litellm version at implementation time.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | litellm version verified via PyPI; google extra dependency verified via litellm pyproject.toml; all API patterns verified against litellm source and Nanobot reference implementation |
| Features | HIGH (core) / MEDIUM (VertexAI specifics) | litellm sync/streaming API shape is HIGH — corroborated by Nanobot. VertexAI env var exact names (`VERTEXAI_PROJECT` vs `VERTEX_PROJECT`) are MEDIUM — minor naming inconsistencies exist across litellm versions |
| Architecture | HIGH | Based on direct codebase analysis of all 5 affected files + Nanobot reference; centralized llm_client pattern is proven |
| Pitfalls | HIGH (most) / MEDIUM (Gemini system messages, token counter accuracy) | ADC, drop_params, streaming incompatibility are HIGH — directly observed in code. Gemini system message conversion is MEDIUM — litellm behavior is version-dependent |

**Overall confidence:** HIGH

### Gaps to Address

- **Exact VertexAI env var names:** litellm accepts both `VERTEXAI_PROJECT` and `VERTEX_PROJECT` but behavior may differ by version. Verify against `litellm.vertex_llm_base.py` source at the pinned version before Phase 1 smoke test.
- **`litellm.token_counter()` accuracy for Gemini:** Documented fallback to `cl100k_base` for unknown tokenizers. Verify whether litellm 1.81.14 has a native Gemini tokenizer or still falls back. Affects token budget accuracy (acceptable either way, but worth documenting).
- **`_stream_with_summary_filter()` chunk boundary behavior:** This method buffers streaming chunks to detect `<SUMMARY>...</SUMMARY>` tags. litellm chunk sizes may differ from Anthropic's `text_stream` granularity. Needs empirical testing with long responses, not resolvable from static analysis.
- **Gemini system message conversion:** litellm's `role: system` → `system_instruction` conversion for Gemini is mentioned in multiple GitHub issues as version-dependent. Verify at implementation time against the installed version.

## Sources

### Primary (HIGH confidence)
- litellm PyPI `1.81.14`: https://pypi.org/pypi/litellm/json
- litellm `pyproject.toml` (google extra): https://raw.githubusercontent.com/BerriAI/litellm/main/pyproject.toml
- litellm `__init__.py` (vertex_project, vertex_location, drop_params): https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/__init__.py
- litellm `vertex_llm_base.py` (auth patterns, env vars): https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/llms/vertex_ai/vertex_llm_base.py
- litellm `main.py` (streaming, response types): https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/main.py
- Nanobot `litellm_provider.py` (reference implementation): `/Users/knakanishi/Repositories/FastCode/nanobot/nanobot/providers/litellm_provider.py`
- Direct codebase analysis: `fastcode/answer_generator.py`, `fastcode/query_processor.py`, `fastcode/iterative_agent.py`, `fastcode/repo_selector.py`, `fastcode/repo_overview.py`, `fastcode/llm_utils.py`, `fastcode/utils.py`
- `google-cloud-aiplatform` PyPI (deprecation notice): https://pypi.org/pypi/google-cloud-aiplatform/json

### Secondary (MEDIUM confidence)
- litellm VertexAI docs: https://docs.litellm.ai/docs/providers/vertex — env var names, model format patterns
- litellm token counting docs: https://docs.litellm.ai/docs/completion/token_usage — `litellm.token_counter()` API
- Gemini system message handling: litellm GitHub issues — version-dependent conversion behavior

---
*Research completed: 2026-02-24*
*Ready for roadmap: yes*
