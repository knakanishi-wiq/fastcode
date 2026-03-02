---
phase: 11-sqlite-schema-and-db-init
plan: 01
subsystem: database
tags: [sqlite, fts5, bm25, triggers, schema]

# Dependency graph
requires: []
provides:
  - "fastcode/db.py: init_db() function creating chunks, sources, chunks_fts tables with FTS5 sync triggers"
  - "tests/test_db.py: 7 automated tests covering schema, triggers, and idempotency"
affects: [12-indexer, 13-bm25-retriever, 14-embedding-cache]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SQLite FTS5 content table (content=chunks) linked to chunks table via content_rowid=id"
    - "Three-trigger FTS sync pattern: chunks_ai (INSERT), chunks_ad (DELETE), chunks_au (UPDATE)"
    - "executescript() for idempotent DDL — single call with CREATE IF NOT EXISTS blocks"

key-files:
  created:
    - fastcode/db.py
    - tests/test_db.py
  modified: []

key-decisions:
  - "Used executescript() for all DDL instead of individual execute() calls — cleaner for multi-statement DDL"
  - "WAL mode omitted — single-process CLI tool does not require concurrent read access"
  - "FTS5 content-linked table (content=chunks) chosen over contentless — allows content retrieval from FTS query without joining back to chunks"
  - "PRAGMA foreign_keys = ON set after executescript() — executescript() commits implicitly and resets connection state"

patterns-established:
  - "init_db(): db_path str -> sqlite3.Connection; caller reuses returned connection immediately"
  - "In-memory :memory: databases used exclusively in tests — no disk I/O, no teardown required"

requirements-completed: [STOR-01, STOR-02, STOR-03]

# Metrics
duration: 2min
completed: 2026-02-27
---

# Phase 11 Plan 01: SQLite Schema and DB Init Summary

**SQLite init module with chunks/sources tables, FTS5 content-linked virtual table, and INSERT/DELETE/UPDATE sync triggers — all idempotent via CREATE IF NOT EXISTS**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-27T03:28:48Z
- **Completed:** 2026-02-27T03:30:24Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `fastcode/db.py` provides `init_db(db_path)` that creates the full schema in one idempotent `executescript()` call
- FTS5 virtual table `chunks_fts` content-linked to `chunks` with three sync triggers keeping the index current
- 7-test suite covering column schemas, FTS table existence, insert/delete trigger behaviour, and idempotency on both `:memory:` and file-backed databases

## Task Commits

Each task was committed atomically:

1. **Task 1: Create fastcode/db.py — SQLite schema and init function** - `2868055` (feat)
2. **Task 2: Create tests/test_db.py — schema, trigger, and idempotency tests** - `f11752b` (test)

## Files Created/Modified
- `fastcode/db.py` - SQLite init module; exposes `init_db(db_path) -> sqlite3.Connection`
- `tests/test_db.py` - 7 pytest tests for schema, FTS5 triggers, and idempotency

## Decisions Made
- Used `executescript()` for all DDL (single call, cleaner than N individual `execute()` calls for schema setup)
- WAL mode omitted — single-process CLI tool does not benefit from WAL; reduces complexity
- FTS5 `content=chunks` (content-linked) chosen over contentless — retriever Phase 13 can fetch chunk text from FTS without a separate join
- `PRAGMA foreign_keys = ON` issued as a separate `execute()` after `executescript()` because `executescript()` commits implicitly and the PRAGMA must be set on the live connection

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `fastcode/db.py` is importable; `init_db()` ready for Phase 12 indexer to call on startup
- Schema contract established: chunks (7 cols), sources (4 cols), chunks_fts (FTS5)
- All 7 tests pass; CI green

---
*Phase: 11-sqlite-schema-and-db-init*
*Completed: 2026-02-27*
