---
phase: 03-non-streaming-migration
plan: 01
subsystem: llm-client
tags: [litellm, openai, anthropic, vertexai, llm_client, query_processor]

# Dependency graph
requires:
  - phase: 02-core-infrastructure
    provides: fastcode/llm_client.py with completion(), DEFAULT_MODEL, count_tokens()
provides:
  - query_processor.py migrated off direct openai/anthropic clients to llm_client.completion()
affects: [03-non-streaming-migration, 04-streaming-migration]

# Tech tracking
tech-stack:
  added: []
  patterns: [All LLM calls in query_processor.py route through llm_client.completion() with llm_client.DEFAULT_MODEL]

key-files:
  created: []
  modified:
    - fastcode/query_processor.py

key-decisions:
  - "Remove os import entirely since all usages were in the dead constructor code being removed"
  - "Replace provider dispatch + _call_openai/_call_anthropic with single _call_llm() method calling llm_client.completion()"
  - "_should_use_llm_enhancement guard simplified from 'not use_llm_enhancement or llm_client is None' to 'not use_llm_enhancement' since llm_client is now module-level not instance-level"

patterns-established:
  - "LLM call pattern: llm_client.completion(model=llm_client.DEFAULT_MODEL, messages=[...], temperature=..., max_tokens=...)"
  - "No instance-level LLM client — module import provides the client"

requirements-completed: [MIGR-01, MIGR-05]

# Metrics
duration: 2min
completed: 2026-02-24
---

# Phase 3 Plan 01: Migrate query_processor.py to llm_client Summary

**query_processor.py migrated off broken openai/anthropic direct clients to llm_client.completion() with single _call_llm() method, removing 71 lines of dead provider dispatch code**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T06:58:15Z
- **Completed:** 2026-02-24T07:00:32Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Removed broken import (`from .llm_utils import openai_chat_completion`) that was causing module import failure
- Removed dead constructor state: `provider`, `model`, `api_key`, `anthropic_api_key`, `base_url`, `llm_client`, `_initialize_llm_client`
- Replaced `_call_openai` and `_call_anthropic` methods with single `_call_llm()` routing through `llm_client.completion()`
- Updated all provider dispatch blocks and `self.llm_client` guards to use the new pattern
- All 10 tests in `tests/test_llm_client.py` pass after migration

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate query_processor.py to llm_client** - `f41252b` (refactor)
2. **Task 2: Verify with test suite** - (no commit needed — verification only, tests passed)

## Files Created/Modified
- `fastcode/query_processor.py` - Removed direct openai/anthropic clients, replaced with llm_client.completion()

## Decisions Made
- Removed `os` import entirely since all usages (`os.getenv("MODEL")`, `os.getenv("OPENAI_API_KEY")`, etc.) were in the dead constructor code being deleted
- Simplified `_should_use_llm_enhancement` guard from `not self.use_llm_enhancement or self.llm_client is None` to `not self.use_llm_enhancement` — no instance-level client to check anymore
- `_call_llm` uses `llm_client.DEFAULT_MODEL` directly, consistent with the module-level design of llm_client

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `query_processor.py` is now importable and routes all LLM calls through VertexAI via litellm
- 4 remaining files still broken by deleted llm_utils: `repo_selector.py`, `iterative_agent.py`, `repo_overview.py`, `answer_generator.py`
- Phase 3 plans 02-04 will migrate those files

---
*Phase: 03-non-streaming-migration*
*Completed: 2026-02-24*
