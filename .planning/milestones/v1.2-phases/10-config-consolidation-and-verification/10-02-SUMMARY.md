---
phase: 10-config-consolidation-and-verification
plan: "02"
subsystem: testing
tags: [smoke-tests, vertexai, embedder, streaming, litellm, gcp, adc]

# Dependency graph
requires:
  - phase: 10-config-consolidation-and-verification
    provides: DEBT-04 resolved; MODEL env var removed; all LLM callers use llm_client.DEFAULT_MODEL
  - phase: 09-dockerfile-and-code-cleanup
    provides: embed_text() task_type kwarg explicit; retriever.py uses RETRIEVAL_QUERY
provides:
  - Live smoke test confirming CODE_RETRIEVAL_QUERY task_type accepted by gemini-embedding-001 API
  - Live smoke test confirming _stream_with_summary_filter() does not leak SUMMARY tags into displayed output
  - DEBT-03 and DEBT-05 closed with live GCP findings documented as comments
affects: [any phase touching embedder, answer_generator, or multi-turn conversation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Smoke tests gated by @pytest.mark.skipif(not os.environ.get('VERTEXAI_PROJECT'), ...) — skip in CI, run live with ADC credentials"
    - "FINDING comments in test docstrings document live GCP behavior at execution date"

key-files:
  created: []
  modified:
    - tests/test_embedder_smoke.py
    - tests/test_vertexai_smoke.py

key-decisions:
  - "DEBT-03 confirmed live: gemini-embedding-001 accepts CODE_RETRIEVAL_QUERY task_type — asymmetric pairing at retriever.py line 734 is valid"
  - "DEBT-05 confirmed live: _stream_with_summary_filter() correctly suppresses SUMMARY tags — no leakage observed"
  - "Tests ran live (not skipped) because .env file has VERTEXAI_PROJECT set — FINDING comments reflect actual GCP API behavior"

patterns-established:
  - "FINDING comments pattern: docstring records date and observed behavior from live GCP run"

requirements-completed: [DEBT-03, DEBT-05]

# Metrics
duration: 3min
completed: 2026-02-26
---

# Phase 10 Plan 02: Live Smoke Tests for CODE_RETRIEVAL_QUERY and Streaming Filter Summary

**Two live GCP smoke tests added and verified: DEBT-03 confirms gemini-embedding-001 accepts asymmetric CODE_RETRIEVAL_QUERY task_type; DEBT-05 confirms _stream_with_summary_filter() correctly suppresses SUMMARY tags with no leakage**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-26T22:19:30Z
- **Completed:** 2026-02-26T22:22:43Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `test_code_retrieval_query_returns_valid_embedding` to `TestEmbedderSmoke` — live run passed, confirmed CODE_RETRIEVAL_QUERY accepted by gemini-embedding-001 returning a valid 3072-dim L2-normalized vector
- Added `test_stream_with_summary_filter_multi_turn` to `TestVertexAISmoke` — live run passed, confirmed _stream_with_summary_filter() did not leak `<SUMMARY>` or `</SUMMARY>` tags into displayed chunks
- Both tests ran live against GCP (not skipped) because .env has VERTEXAI_PROJECT set; FINDING comments in docstrings document observed behavior
- All 6 smoke tests now pass: 2 embedder + 4 vertexai (including the config error test that always runs)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add DEBT-03 CODE_RETRIEVAL_QUERY smoke test to test_embedder_smoke.py** - `bae7b90` (feat)
2. **Task 2: Add DEBT-05 streaming filter smoke test to test_vertexai_smoke.py** - `fd9ae0a` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `tests/test_embedder_smoke.py` - Added `test_code_retrieval_query_returns_valid_embedding`; uses `task_type="CODE_RETRIEVAL_QUERY"` with Python code snippet input; FINDING documents live GCP result
- `tests/test_vertexai_smoke.py` - Added `test_stream_with_summary_filter_multi_turn`; passes `dialogue_history=[]` to trigger filter path; asserts no SUMMARY tag leakage; FINDING documents live GCP result

## Decisions Made

- Tests ran live (VERTEXAI_PROJECT in .env) rather than skipping — FINDING comments reflect actual API behavior not hypothetical
- Used `dialogue_history=[]` (empty list, not None) to satisfy the `is not None` check at answer_generator.py line 244 that engages `_stream_with_summary_filter()`
- FINDING comments use the docstring (not inline comments) to keep the discovery notes co-located with the test purpose

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — both tests passed on first run. Live GCP credentials available via .env file.

## User Setup Required

None - no external service configuration required. Tests skip gracefully without VERTEXAI_PROJECT.

## Next Phase Readiness

- DEBT-03 and DEBT-05 closed with live GCP findings documented
- Phase 10 (v1.2 Config Consolidation and Verification) is now complete — DEBT-04, DEBT-03, and DEBT-05 all resolved
- All three plans in Phase 10 are complete; v1.2 milestone can be closed

---
*Phase: 10-config-consolidation-and-verification*
*Completed: 2026-02-26*

## Self-Check: PASSED

- tests/test_embedder_smoke.py: FOUND
- tests/test_vertexai_smoke.py: FOUND
- 10-02-SUMMARY.md: FOUND
- Task commit bae7b90: FOUND
- Task commit fd9ae0a: FOUND
