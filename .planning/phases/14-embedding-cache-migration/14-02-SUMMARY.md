---
phase: 14-embedding-cache-migration
plan: "02"
subsystem: cleanup
tags: [diskcache, pyproject, cli, readme]

# Dependency graph
requires:
  - phase: 14-01
    provides: SQLite embedding_cache in CodeEmbedder (diskcache callers now zero for embeddings)
provides:
  - "fastcode/cache.py: disk backend removed from CacheManager; get_embedding/set_embedding dead code deleted"
  - "pyproject.toml: diskcache dependency removed"
  - "main.py: --clear-cache flag on index command (truncates embedding_cache)"
  - "README.md: Known Consequences section with migration instructions"
affects: []

# Tech tracking
tech-stack:
  removed: [diskcache]
  patterns:
    - "Warning log when cache.backend='disk' configured — graceful degradation, not crash"
    - "`--clear-cache` flag on index command uses inline sqlite3.connect() (not FastCode.retriever._db_conn)"

key-files:
  created: []
  modified:
    - fastcode/cache.py
    - pyproject.toml
    - main.py
    - README.md

key-decisions:
  - "Removed get_embedding() and set_embedding() from CacheManager — never called, dead code"
  - "Removed cache_embeddings, cache_directory, max_size_mb attributes — disk-only, now unused"
  - "Removed Path import — only used for disk cache directory creation"
  - "--clear-cache uses inline sqlite3.connect(db_path) before FastCode.retriever is fully init'd — avoids order dependency"
  - "README Known Consequences section placed before License section"

requirements-completed: [EMB-01, EMB-02]

# Metrics
duration: 2min
completed: 2026-03-02
---

# Phase 14 Plan 02: diskcache Removal + --clear-cache CLI Summary

**diskcache removed from pyproject.toml and CacheManager; --clear-cache flag added to index command; README updated**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-02
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

1. Removed `from diskcache import Cache as DiskCache` from `fastcode/cache.py`
2. Replaced disk backend init block with warning + `self.enabled = False`
3. Removed all `if self.backend == "disk":` branches from get/set/delete/clear/list_sessions/get_stats
4. Deleted dead `get_embedding()` and `set_embedding()` methods
5. Removed orphaned `cache_embeddings`, `cache_directory`, `max_size_mb` attributes and `Path` import
6. Removed `diskcache` from `pyproject.toml` dependencies
7. Added `--clear-cache` flag to `index` CLI command in `main.py`
8. Added Known Consequences section to README.md with re-index and --clear-cache instructions

## Test Results

```
Full suite: 42 passed, 0 failed
python main.py index --help: shows --clear-cache flag
grep "diskcache" fastcode/cache.py pyproject.toml: no import lines
```

## Self-Check: PASSED
