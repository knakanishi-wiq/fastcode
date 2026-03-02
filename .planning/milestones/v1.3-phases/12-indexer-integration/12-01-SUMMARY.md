---
phase: 12-indexer-integration
plan: "01"
subsystem: database
tags: [sqlite, indexer, bm25, fts5, pathspec, sha256, change-detection]

# Dependency graph
requires:
  - phase: 11-sqlite-schema-and-db-init
    provides: init_db(), sources table, chunks table, chunks_fts FTS5 virtual table
provides:
  - index_repo(repo_path, db_path) module-level function in fastcode/indexer.py
  - SQLite-backed chunk writing with mtime_ns + SHA-256 change detection
  - .gitignore filtering via pathspec, hidden dir pruning, per-file transactions
affects:
  - 13-fts5-bm25-retriever (consumes chunks table for FTS5 BM25 queries)
  - 14-embedding-cache (shares SQLite DB path convention)

# Tech tracking
tech-stack:
  added: [pathspec (gitignore), os.walk, hashlib.sha256]
  patterns:
    - mtime_ns fast-path before hash comparison for skip detection
    - per-file SQLite transaction with DELETE+INSERT (cascade clears chunks)
    - language=='unknown' guard to filter unsupported file extensions

key-files:
  created: [tests/test_indexer_sqlite.py]
  modified: [fastcode/indexer.py]

key-decisions:
  - "Skip files where parse_result.language=='unknown' (CodeParser never returns None for unknown extensions — it returns a generic result)"
  - "Use pathspec 'gitignore' pattern name (not deprecated 'gitwildmatch') for .gitignore parsing"
  - "Module-level logger = logging.getLogger(__name__) added at top of indexer.py"

patterns-established:
  - "Per-file transaction: DELETE FROM sources WHERE path=? (cascades to chunks), then INSERT sources + chunks"
  - "mtime_ns fast-path → sha256 comparison → full re-index flow for change detection"
  - "seen_paths set after walk to identify and DELETE removed files"

requirements-completed: [IDX-01, IDX-02]

# Metrics
duration: 4min
completed: 2026-02-27
---

# Phase 12 Plan 01: Indexer SQLite Integration Summary

**index_repo() with mtime_ns + SHA-256 change detection writes parsed code chunks to SQLite sources/chunks tables, replacing in-memory BM25 corpus construction**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-27T06:34:32Z
- **Completed:** 2026-02-27T06:38:40Z
- **Tasks:** 3 (TDD: RED + GREEN + REFACTOR)
- **Files modified:** 2

## Accomplishments
- index_repo(repo_path, db_path) implemented at module level in fastcode/indexer.py
- IDX-01: parsed code chunks (classes, functions, fallback whole-file) written to chunks table
- IDX-02: mtime_ns fast-path + SHA-256 content hash change detection; UPDATE-only for mtime drift
- .gitignore filtering via pathspec, hidden dir pruning via dirs[:] in-place modification
- 8 pytest tests covering all spec scenarios; 31/31 full suite green

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — Write failing tests** - `72b68f5` (test)
2. **Task 2: GREEN — Implement index_repo()** - `f922851` (feat)
3. **Task 3: REFACTOR** - No changes needed; code was clean on first pass

_Note: TDD tasks have RED and GREEN commits; REFACTOR had no diff._

## Files Created/Modified
- `fastcode/indexer.py` - Added module-level imports (os, sqlite3, pathspec, init_db, logger) and index_repo() function at bottom
- `tests/test_indexer_sqlite.py` - 8 pytest tests for IDX-01 and IDX-02

## Decisions Made
- Skip files where `parse_result.language == 'unknown'`: CodeParser._parse_generic() never returns None for unknown extensions — returns a FileParseResult with language='unknown'. Checking for 'unknown' matches the plan's intent of "unsupported extension → skip silently".
- Use pathspec `'gitignore'` pattern name: `'gitwildmatch'` is deprecated in the installed pathspec version; switching eliminates DeprecationWarning.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CodeParser returns FileParseResult(language='unknown') for unsupported extensions, not None**
- **Found during:** Task 2 (GREEN — test_empty_directory failed: test.db was being indexed)
- **Issue:** Plan said "treat None result as unsupported extension → skip silently", but CodeParser._parse_generic() returns a populated FileParseResult for unknown extensions (`.db`, `.log`, etc.)
- **Fix:** Added `or parse_result.language == "unknown"` guard in the skip condition
- **Files modified:** fastcode/indexer.py
- **Verification:** test_empty_directory passes; test_gitignore_respected passes
- **Committed in:** f922851 (Task 2 GREEN commit)

**2. [Rule 1 - Bug] pathspec 'gitwildmatch' is deprecated**
- **Found during:** Task 2 (test output showed DeprecationWarning for GitWildMatchPattern)
- **Issue:** pathspec warns that 'gitwildmatch' pattern name is deprecated in favour of 'gitignore'
- **Fix:** Changed both `PathSpec.from_lines()` calls to use `"gitignore"` pattern name
- **Files modified:** fastcode/indexer.py
- **Verification:** All 8 tests pass with 0 pathspec warnings
- **Committed in:** f922851 (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- chunks and sources tables are populated by index_repo() — Phase 13 FTS5 BM25 retriever can now query chunks_fts
- DB path convention still TBD (noted in STATE.md pending decisions); index_repo() accepts explicit db_path so any convention works
- Full test suite (31 tests) green with no regressions

---
*Phase: 12-indexer-integration*
*Completed: 2026-02-27*
