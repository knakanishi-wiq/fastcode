---
phase: 09-dockerfile-and-code-cleanup
plan: 02
subsystem: infra
tags: [python, cleanup, tech-debt, embedder, litellm]

# Dependency graph
requires:
  - phase: 07-litellm-embedder-integration
    provides: embed_text() with task_type parameter in embedder.py
provides:
  - Clean __init__.py without dead OS-detection block (DEBT-01)
  - Explicit task_type="RETRIEVAL_QUERY" kwarg at retriever.py line 415 (DEBT-02)
affects: [10-debt-consolidation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Explicit keyword arguments at embed_text call sites for clarity and runtime safety"

key-files:
  created: []
  modified:
    - fastcode/__init__.py
    - fastcode/retriever.py

key-decisions:
  - "Delete all six dead lines (import os, import platform, blank, if-block with 4 lines) rather than leaving stubs — F401 unused import would fail linting"
  - "Use task_type='RETRIEVAL_QUERY' (uppercase) — matches embedder.py default exactly, avoids runtime task_type validation error"

patterns-established:
  - "All embed_text() call sites must pass task_type as an explicit keyword argument (not rely on default)"

requirements-completed: [DEBT-01, DEBT-02]

# Metrics
duration: 3min
completed: 2026-02-26
---

# Phase 09 Plan 02: Code Cleanup (DEBT-01, DEBT-02) Summary

**Removed 8-line dead Darwin platform import block from __init__.py and made task_type="RETRIEVAL_QUERY" explicit at retriever.py line 415**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-26T00:00:00Z
- **Completed:** 2026-02-26T00:03:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Deleted `import os`, `import platform`, and the `if platform.system() == 'Darwin':` block (lines 6-13 of __init__.py) — dead code since sentence-transformers was removed in v1.1
- Made `task_type="RETRIEVAL_QUERY"` explicit at retriever.py line 415 — intent now visible at call site, no behavior change
- `python3 -c "import fastcode; print('OK')"` still exits 0 after deletion

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove dead platform import block from __init__.py (DEBT-01)** - `231eab9` (fix)
2. **Task 2: Make task_type explicit at retriever.py line 415 (DEBT-02)** - `0506cba` (fix)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified

- `fastcode/__init__.py` - Removed 9 lines: import os, import platform, blank line, and the Darwin if-block setting TOKENIZERS_PARALLELISM/OMP_NUM_THREADS/OPENBLAS_NUM_THREADS/MKL_NUM_THREADS
- `fastcode/retriever.py` - Line 415: added `task_type="RETRIEVAL_QUERY"` as explicit kwarg to embed_text() call

## Decisions Made

- Deleted all six dead lines (not just the if-block) — both `import os` and `import platform` were only used by the dead block; leaving either would be an unused import (F401)
- Used uppercase `RETRIEVAL_QUERY` — matches embedder.py signature default exactly; lowercase would cause a runtime validation error

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DEBT-01 and DEBT-02 fully resolved
- Phase 9 Plan 02 complete; Phase 9 is now ready to close out if no further plans remain
- DEBT-03, DEBT-04, DEBT-05 remain for Phase 10 (require live GCP credentials for verification)

---
*Phase: 09-dockerfile-and-code-cleanup*
*Completed: 2026-02-26*
