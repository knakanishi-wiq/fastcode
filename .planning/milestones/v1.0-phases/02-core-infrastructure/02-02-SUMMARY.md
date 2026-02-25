---
phase: 02-core-infrastructure
plan: "02"
subsystem: infra
tags: [litellm, dead-code-removal, llm_utils]

# Dependency graph
requires:
  - phase: 02-core-infrastructure
    provides: "llm_client.py with litellm.drop_params=True (02-01)"
provides:
  - "fastcode/llm_utils.py deleted — no longer exists in repository"
affects: [phase-03-caller-migration, phase-04-streaming-migration]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified: []
  deleted:
    - fastcode/llm_utils.py

key-decisions:
  - "Delete llm_utils.py with callers still present (user-approved) — app intentionally broken until Phase 3/4 migrations complete"
  - "max_tokens fallback logic in llm_utils superseded by litellm.drop_params=True set in llm_client.py"

patterns-established: []

requirements-completed: [INFRA-03]

# Metrics
duration: 2min
completed: 2026-02-24
---

# Phase 2 Plan 02: Delete llm_utils.py Summary

**Deleted fastcode/llm_utils.py (openai_chat_completion wrapper) — max_tokens fallback logic superseded by litellm.drop_params=True in llm_client.py**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T03:19:10Z
- **Completed:** 2026-02-24T03:21:03Z
- **Tasks:** 1
- **Files modified:** 1 (deleted)

## Accomplishments
- Deleted fastcode/llm_utils.py — dead code that was only needed for manual max_tokens/max_completion_tokens fallback
- litellm.drop_params=True (set in llm_client.py, 02-01) makes this wrapper unnecessary
- 5 callers identified in fastcode/ (repo_selector.py, iterative_agent.py, repo_overview.py, answer_generator.py, query_processor.py) — intentionally left broken pending Phase 3/4 migration

## Task Commits

Each task was committed atomically:

1. **Task 1: Verify no imports of llm_utils exist, then delete the file** - `ae3dc0e` (refactor)

**Plan metadata:** (to be added after this summary commit)

## Files Created/Modified
- `fastcode/llm_utils.py` - DELETED. Was: OpenAI-compatible chat completion wrapper with max_tokens/max_completion_tokens fallback via BadRequestError handling.

## Decisions Made
- **Delete with callers present (user override):** User explicitly approved proceeding despite 5 files in fastcode/ still importing from llm_utils. App is intentionally broken until Phase 3/4 migrations update those callers to use llm_client.py.
- **No stub/shim needed:** The callers will be rewritten to use litellm directly in Phase 3/4; a stub would only delay discovery of the breakage.

## Deviations from Plan

None — plan executed exactly as written (with user override applied for the "stop if callers found" guard).

**Note on user override:** The plan stated "If any matches are found, STOP and report them." The user pre-approved skipping this guard with the message: "They have explicitly approved proceeding with the deletion. The app will be broken until Phase 3/4 migrations complete — this is acceptable."

## Issues Encountered
- Test suite fails after deletion (11/12 tests fail) because `fastcode/__init__.py` import chain reaches `repo_overview.py` which imports `llm_utils`. This is expected and pre-approved. The 1 passing test (`test_missing_project_raises_config_error`) confirms litellm-native code paths still work.
- `test_happy_path_returns_valid_response` fails due to real GCP call with "test-project" — this was failing before the deletion as well (not caused by this change).

## Next Phase Readiness
- llm_utils.py is deleted — Phase 3/4 callers must migrate to `from fastcode.llm_client import completion`
- 5 files require migration: repo_selector.py, iterative_agent.py, repo_overview.py, answer_generator.py, query_processor.py
- All 5 files use `openai_chat_completion(client, max_tokens=N, **kwargs)` — migration pattern: replace with `litellm.completion(model=..., max_tokens=N, **kwargs)` and remove the `client` argument

---
*Phase: 02-core-infrastructure*
*Completed: 2026-02-24*
