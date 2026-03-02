# Phase 12: Indexer Integration - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the existing file parser/chunker to write all chunks into the SQLite DB (Phase 11),
with content-hash-based skip logic for unchanged files. This phase delivers `fastcode/indexer.py`
with a single public function `index_repo()`. CLI wiring is a separate phase.

</domain>

<decisions>
## Implementation Decisions

### Change Detection Strategy
- Use mtime_ns as a fast-path: if mtime unchanged since last index, skip hashing entirely
- If mtime has changed, compute SHA-256 of full file content and compare to stored content_hash
- Full file content hash — no sampling shortcuts
- Detect and remove deleted files: after walking the filesystem, delete any `sources` row whose
  path no longer exists on disk (ON DELETE CASCADE handles the chunks cleanup automatically)

### Partial Update Behavior
- When a file changes: delete the `sources` row (cascade deletes all chunks), then reinsert
  the source record and all new chunks. No chunk-level diffing.
- Transaction scope: one transaction per file — if indexing fails mid-repo, already-processed
  files are committed and a retry starts from the first unprocessed file
- On parse error for a single file: log a WARNING and skip the file; continue indexing the rest
- Return a stats dict with keys: `indexed`, `skipped`, `deleted`, `errors` (counts)

### Indexer Invocation & Output
- Public interface: `index_repo(repo_path: str, db_path: str) -> dict`
- `index_repo()` calls `init_db()` internally — callers just pass a path
- Log at INFO level for each file action (indexed / skipped / deleted), WARNING for errors
- Module-level function only; no CLI wiring in this phase

### File Filtering Scope
- Respect `.gitignore`: skip paths matched by the repo's `.gitignore` rules
  (use `pathspec` library to parse and match)
- Always skip hidden directories (names starting with `.`, e.g. `.git`, `.venv`, `.mypy_cache`)
- Skip files larger than 1MB (default `max_file_size_bytes=1_000_000`); override available
  as a keyword argument for tests
- File extension filtering: delegate to existing parser (unchanged)

### Claude's Discretion
- Exact pathspec integration (gitpython vs pathspec standalone)
- How to walk the directory tree (os.walk vs pathlib.Path.rglob)
- Exact logging message format

</decisions>

<specifics>
## Specific Ideas

- No specific references — standard approach is fine
- The `ON DELETE CASCADE` on `chunks.source_path` from Phase 11 makes the delete-then-reinsert
  pattern trivially correct; the planner should rely on this rather than manual chunk deletion

</specifics>

<deferred>
## Deferred Ideas

- CLI wiring (`fastcode index <path>`) — separate phase
- Configurable file filtering via config file — future configuration phase if needed

</deferred>

---

*Phase: 12-indexer-integration*
*Context gathered: 2026-02-27*
