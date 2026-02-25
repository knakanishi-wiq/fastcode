---
phase: 02-core-infrastructure
plan: 01
subsystem: infra
tags: [litellm, tiktoken, vertexai, llm-client, token-counting]

# Dependency graph
requires:
  - phase: 01-config-and-dependencies
    provides: litellm installed, vertex_ai/ model prefix validated, .env.example configured
provides:
  - fastcode.llm_client module with completion, completion_stream, count_tokens, DEFAULT_MODEL
  - Import-time EnvironmentError for missing VERTEXAI_PROJECT or VERTEXAI_LOCATION
  - litellm.drop_params and litellm.suppress_debug_info set at module level
  - count_tokens with tiktoken cl100k_base fallback for unknown models
affects: [phase-03-fastcode-migration, phase-04-streaming-agent]

# Tech tracking
tech-stack:
  added: [tiktoken (used for token counting fallback)]
  patterns: [TDD red-green, import-time env validation, thin litellm pass-through]

key-files:
  created:
    - fastcode/llm_client.py
    - tests/test_llm_client.py
  modified: []

key-decisions:
  - "count_tokens signature is (model, text) — reversed from utils.count_tokens(text, model) — callers migrating must update argument order"
  - "Import-time EnvironmentError (not at first call) — fail fast pattern for missing GCP config"
  - "No logging, no exception translation, no streaming wrapper — thin pass-through only"
  - "tiktoken cl100k_base fallback for unknown model names in count_tokens"

patterns-established:
  - "TDD: Write failing tests first (RED), then implement (GREEN)"
  - "Module-level side effects for litellm globals — no init() call required"
  - "Env validation at import time — EnvironmentError message includes var name and fix hint"

requirements-completed: [INFRA-01, INFRA-02, INFRA-04, TOKN-01]

# Metrics
duration: 4min
completed: 2026-02-24
---

# Phase 02 Plan 01: LLM Client Module Summary

**Centralized litellm pass-through module with import-time GCP env validation, module-level globals, and tiktoken fallback for vertex_ai/ token counting**

## Performance

- **Duration:** 4min
- **Started:** 2026-02-24T03:10:40Z
- **Completed:** 2026-02-24T03:14:18Z
- **Tasks:** 2 (TDD: RED test commit + GREEN implementation commit)
- **Files modified:** 2

## Accomplishments
- Created `fastcode/llm_client.py` — single import point for all LLM calls in FastCode
- `completion()` and `completion_stream()` are thin pass-throughs to `litellm.completion`
- `count_tokens()` uses litellm's token_counter with tiktoken cl100k_base fallback for unknown models (handles vertex_ai/ prefix without KeyError)
- Import-time EnvironmentError when VERTEXAI_PROJECT or VERTEXAI_LOCATION is missing — fail fast, not at first call
- `litellm.drop_params = True` and `litellm.suppress_debug_info = True` set as module-level side effects
- 10 unit tests covering all contract behaviors — all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing tests for llm_client module contract** - `a186feb` (test)
2. **Task 2: Implement fastcode/llm_client.py to pass all tests** - `934ac5c` (feat)

**Plan metadata:** (docs: to be committed)

_Note: TDD tasks have two commits — RED (failing tests) then GREEN (implementation)_

## Files Created/Modified
- `fastcode/llm_client.py` - Centralized LLM module exporting completion, completion_stream, count_tokens, DEFAULT_MODEL
- `tests/test_llm_client.py` - 10 unit tests covering import validation, module globals, token counting, function signatures

## Decisions Made
- `count_tokens(model, text)` signature reversed from `utils.count_tokens(text, model)` — consistent with litellm's own token_counter API; callers migrating from utils must update argument order
- Import-time validation chosen over lazy validation — fail fast before any LLM call is attempted
- tiktoken `cl100k_base` selected as fallback encoding for unknown models (standard GPT-3/4 tokenizer, reasonable approximation)
- No wrapper or translation layer — exceptions from litellm bubble up raw, matching litellm's own API surface

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- None. All 10 tests passed on first run of the implementation.

## User Setup Required
None - no external service configuration required beyond what Phase 01 established.

## Next Phase Readiness
- `fastcode.llm_client` ready for use in Phase 3 migration of direct openai/anthropic call sites
- Phase 3 migrations can be mechanical: `from fastcode.llm_client import completion` + update arg order for any count_tokens calls
- Phase 4 streaming agent can use `completion_stream()` directly

## Self-Check: PASSED

- FOUND: fastcode/llm_client.py
- FOUND: tests/test_llm_client.py
- FOUND: 02-01-SUMMARY.md
- FOUND: commit a186feb (test: failing tests)
- FOUND: commit 934ac5c (feat: implementation)

---
*Phase: 02-core-infrastructure*
*Completed: 2026-02-24*
