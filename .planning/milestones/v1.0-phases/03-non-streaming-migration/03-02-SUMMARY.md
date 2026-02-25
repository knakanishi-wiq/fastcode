---
phase: 03-non-streaming-migration
plan: 02
subsystem: api
tags: [litellm, vertexai, llm_client, migration, repo_selector]

# Dependency graph
requires:
  - phase: 03-01
    provides: query_processor.py migrated to llm_client

provides:
  - repo_selector.py with no openai/anthropic imports, LLM calls via llm_client.completion()
  - _call_llm() replacing _call_openai() and _call_anthropic() in RepositorySelector

affects:
  - 03-03-PLAN (iterative_agent.py migration)
  - 03-04-PLAN (repo_overview.py, answer_generator.py migration)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Provider dispatch removed: single _call_llm() method using llm_client.completion() with llm_client.DEFAULT_MODEL"
    - "Dead constructor state removed: no more per-instance API keys, provider strings, or client objects"
    - "Guard clauses removed: llm_client module always available, errors bubble up as exceptions"

key-files:
  created: []
  modified:
    - fastcode/repo_selector.py

key-decisions:
  - "Remove both select_relevant_files and select_relevant_repos dispatch blocks (not just the first) — both had provider branches calling _call_openai/_call_anthropic"
  - "Remove if not self.llm_client guard in select_relevant_repos as well — the module is always available"
  - "os import removed entirely — all usages were in dead constructor code"

patterns-established:
  - "Pattern: All LLM calls in RepositorySelector route through llm_client.completion() with llm_client.DEFAULT_MODEL"

requirements-completed: [MIGR-04, MIGR-05]

# Metrics
duration: 2min
completed: 2026-02-24
---

# Phase 03 Plan 02: repo_selector.py Migration Summary

**repo_selector.py stripped of all openai/anthropic/dotenv imports and provider dispatch, now routing file and repo selection LLM calls through llm_client.completion() via the centralized litellm module**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T06:24:06Z
- **Completed:** 2026-02-24T06:26:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Removed 5 banned imports (openai, anthropic, dotenv, llm_utils, os) and added `from fastcode import llm_client`
- Deleted dead constructor fields: provider, model, api_key, anthropic_api_key, base_url, llm_client, _initialize_client
- Replaced both provider dispatch blocks (in `select_relevant_files` and `select_relevant_repos`) with `self._call_llm(prompt)`
- Replaced `_call_openai` and `_call_anthropic` with single `_call_llm()` using `llm_client.completion()`
- All 10 tests in `tests/test_llm_client.py` pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate repo_selector.py to llm_client** - `821bde6` (refactor)
2. **Task 2: Verify repo_selector.py migration with test suite** - (no code changes, tests passed)

## Files Created/Modified

- `fastcode/repo_selector.py` - Removed all provider-specific client code; LLM calls now route through llm_client

## Decisions Made

- Removed dispatch blocks in both `select_relevant_files` and `select_relevant_repos` — the plan called out `select_relevant_files` explicitly, but `select_relevant_repos` had an identical pattern that also needed replacing (Rule 1 auto-fix)
- Removed `if not self.llm_client:` guard in `select_relevant_repos` as well as `select_relevant_files` — both guards were predicated on the old instance-level client that no longer exists
- `os` import removed since all usages were exclusively in the dead constructor code

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed second provider dispatch block in select_relevant_repos**
- **Found during:** Task 1 (Migrate repo_selector.py to llm_client)
- **Issue:** The plan's Step 5 targeted only the dispatch in `select_relevant_files`, but `select_relevant_repos` contained an identical `if self.provider == "openai" / elif self.provider == "anthropic"` block with a dead `self.llm_client` guard that also needed removal
- **Fix:** Replaced both dispatch blocks with `self._call_llm(prompt)`; removed `if not self.llm_client:` guard in `select_relevant_repos`
- **Files modified:** fastcode/repo_selector.py
- **Verification:** Static grep shows no banned patterns; tests pass
- **Committed in:** 821bde6

---

**Total deviations:** 1 auto-fixed (Rule 1 — Bug)
**Impact on plan:** Fix was necessary to fully complete the migration — leaving the second dispatch block would have left dead provider references. No scope creep.

## Issues Encountered

None - migration was straightforward after identifying both dispatch locations.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `fastcode/repo_selector.py` fully migrated; 3 files remain broken pending Phase 3/4 migration: `iterative_agent.py`, `repo_overview.py`, `answer_generator.py`
- No blockers for 03-03

---
*Phase: 03-non-streaming-migration*
*Completed: 2026-02-24*
