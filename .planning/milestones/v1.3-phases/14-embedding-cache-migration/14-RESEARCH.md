# Phase 14: Embedding Cache Migration - Research

**Researched:** 2026-03-02
**Domain:** SQLite embedding cache, Python sqlite3, numpy BLOB serialization
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### DiskCache removal
- Remove `diskcache` from `pyproject.toml` entirely — no remaining callers after this phase
- Researcher should grep for all `diskcache` usages in the codebase before planning (caller list now confirmed — see findings)
- Delete the existing DiskCache data directory as part of the migration — document the exact path once discovered by the researcher/executor
- Add a migration note in README (Known Consequences section) — same pattern as v1.1 FAISS reindex note

#### Cache invalidation policy
- Cache entries are **permanent** — embeddings are deterministic for `(content_hash, model)`, no automatic invalidation needed
- Old model entries persist harmlessly when model changes — different model = different cache key, old rows are never retrieved but cause no errors
- **Validate embedding shape on retrieval**: if the cached embedding's dimension doesn't match the expected `embedding_dim`, raise an error (not silently re-embed) — this catches model-switch bugs early

#### Migration path from DiskCache
- **Start fresh** — no migration of existing DiskCache entries to SQLite; clean break
- Full re-index required after upgrade; document as Known Consequence in README
- DiskCache directory path: let executor discover from codebase (grep for DiskCache init in embedder.py) — note: DiskCache init is in `cache.py`, directory config key `cache.cache_directory`, default `./data/cache`
- Deletion of old DiskCache directory: documented manual step in README, not automated cleanup code

#### Cache entry point
- Cache-check logic lives **inside `embed_text()` on `CodeEmbedder`** — same location as current DiskCache check; all callers benefit transparently with zero signature changes
- Storage format: **BLOB of float32 bytes** (`numpy.ndarray.tobytes()`), deserialized via `numpy.frombuffer(..., dtype=float32)` on retrieval — compact, fast, matches schema spec
- `embed_text()` signature **unchanged** — caching is a transparent implementation detail
- `--clear-cache` flag attached to the **`index` CLI command** (`fastcode index --clear-cache`); truncates `embedding_cache` table before indexing begins

### Claude's Discretion
- Exact SQL for `embedding_cache` table DDL (beyond what REQUIREMENTS.md specifies)
- Whether to add `embedding_cache` to `db.py`'s `init_db()` or a separate migration function
- Test structure: TDD (write failing tests first) vs execute-style plan
- Whether `--clear-cache` truncates only `embedding_cache` or also `chunks`/FTS tables

### Deferred Ideas (OUT OF SCOPE)
- `fastcode cache clear` as a standalone CLI command — Phase 14 attaches --clear-cache to `index` only; a dedicated cache management command could be a future phase
- Cache size monitoring / eviction policies — out of scope; cache is append-only for v1.3
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EMB-01 | An `embedding_cache` table in SQLite stores embeddings keyed on `(content_hash, model)` with the embedding stored as a BLOB | SQLite BLOB type stores raw bytes; `numpy.ndarray.tobytes()` + `numpy.frombuffer()` is the standard round-trip pattern (HIGH confidence) |
| EMB-02 | `CodeEmbedder` checks the SQLite `embedding_cache` before calling `litellm.embedding()`; cache hits avoid a VertexAI API round-trip | `embed_text()` can check DB before calling `litellm.embedding()`; connection passed via `__init__` or `set_db()` (HIGH confidence) |
</phase_requirements>

## Summary

Phase 14 replaces the `diskcache`-backed embedding cache with a SQLite `embedding_cache` table.
The change is contained to three files: `fastcode/db.py` (schema addition), `fastcode/embedder.py`
(cache lookup/store in `embed_text()`), and `main.py` (CLI `--clear-cache` flag on the `index` command).
The `diskcache` import in `fastcode/cache.py` is the only remaining consumer; once the cache path
for embeddings is removed from `CacheManager` (which is unused for embeddings anyway — the embed_text
path never calls `cache_manager`), `diskcache` can be removed from `pyproject.toml` entirely.

**Primary recommendation:** Add `embedding_cache` table DDL to `db.py`'s existing `_DDL` string,
pass the DB connection into `CodeEmbedder.__init__()` (or via a setter), and add cache
lookup/store to `embed_text()`. Remove `diskcache` from `pyproject.toml`. Add `--clear-cache`
flag to the `index` CLI command in `main.py`.

## Codebase Findings

### diskcache caller audit (confirmed by grep)

| File | Usage |
|------|-------|
| `fastcode/cache.py` | Only consumer: `from diskcache import Cache as DiskCache` at line 13; `DiskCache(...)` at line 46 |
| All other `.py` files | No diskcache imports or references |

**Key finding:** `CodeEmbedder` in `fastcode/embedder.py` does NOT currently use `CacheManager` or
`diskcache` at all. The embedding cache feature is to be **added** — not migrated from a working
DiskCache path. The `CacheManager` class handles dialogue history, not embedding caching.
`cache_manager.get_embedding()` / `set_embedding()` methods exist in `CacheManager` but are
**never called** by `CodeEmbedder`. This simplifies the plan: add new cache path, remove old
dead code.

### DiskCache directory path

From `cache.py`:
```python
self.cache_directory = self.cache_config.get("cache_directory", "./data/cache")
self.cache = DiskCache(self.cache_directory, size_limit=max_size_bytes)
```

Default: `./data/cache` — this is the directory the README should instruct users to delete.

### Current `embed_text()` / `embed_batch()` flow

```python
def embed_text(self, text: str, task_type: str = "RETRIEVAL_QUERY") -> np.ndarray:
    return self.embed_batch([text], task_type=task_type)[0]

def embed_batch(self, texts, task_type="RETRIEVAL_QUERY") -> np.ndarray:
    # calls litellm.embedding() directly — no cache check
    response = litellm.embedding(model=..., input=batch, task_type=task_type)
```

Cache-check must be inserted into `embed_text()` (single-text path), not `embed_batch()`,
per locked decision. `embed_batch()` continues to call `litellm.embedding()` unchanged.

### SQLite DB connection threading

The indexer is single-threaded. `sqlite3.connect()` default `check_same_thread=True` is fine.
The DB path is `./data/fastcode.db` (Phase 12 decision). `CodeEmbedder` needs a reference to
the connection or the db_path to look up and store embeddings.

**Recommended approach:** Add an optional `db_conn: Optional[sqlite3.Connection]` to
`CodeEmbedder.__init__()`. When `None`, cache is disabled (backward-compatible for tests
that don't need a DB). The caller in `main.py` passes the connection after `init_db()`.

### `--clear-cache` implementation

The `index` command in `main.py` (lines 141–186) calls `fastcode.index_repository()`.
Adding `--clear-cache` flag that calls `conn.execute("DELETE FROM embedding_cache")` before
indexing begins is the minimal approach. Per CONTEXT.md, it truncates `embedding_cache`
only (not `chunks` or FTS tables — those have their own re-index logic via IDX-02).

### `diskcache` removal impact on `CacheManager`

`CacheManager` in `fastcode/cache.py`:
- `cache_manager.get_embedding()` and `cache_manager.set_embedding()` are defined but never called
  by `CodeEmbedder` — these are dead code paths that can be deleted as part of cleanup
- `CacheManager` still handles dialogue history (used by `main.py`) — must NOT be deleted
- Only the `diskcache` backend inside `_initialize_cache()` must be replaced or removed
- Since dialogue history via DiskCache is also affected, clarify: does the plan remove
  DiskCache backend from `CacheManager` or just from the embed path?

**Recommendation:** Per CONTEXT.md "no remaining callers after this phase", the diskcache
dep should be removed. But `CacheManager` still uses `DiskCache` for dialogue history.
This is a **gap**: the planner must decide whether to:
  a) Remove `diskcache` from `CacheManager` too (replace with in-memory or SQLite)
  b) Keep `CacheManager`'s diskcache but document it as a known debt

**Recommendation (Claude's Discretion):** Option (b) is safer for Phase 14 scope.
The CONTEXT.md says "no remaining callers" — but `CacheManager` IS a remaining caller.
The planner should decide to either keep diskcache in `CacheManager` (marking it out-of-scope
for Phase 14) or explicitly remove it. Given the phase boundary definition ("CodeEmbedder
checks SQLite embedding_cache"), option (b) keeps scope tight.

**ACTUALLY — on re-read of CONTEXT.md:** "Remove `diskcache` from `pyproject.toml` entirely —
no remaining callers after this phase." This means Phase 14 MUST remove all diskcache usage.
Since `CacheManager` uses diskcache for dialogue history, the planner must address this.
Options: remove `CacheManager.backend == "disk"` path entirely (breaking dialogue history)
OR migrate `CacheManager`'s disk backend to Python's stdlib `shelve` / plain JSON files.

**Revised recommendation:** The simplest fix is to drop the `backend: disk` path from
`CacheManager` and default dialogue history to `backend: redis` only (with `enabled=False`
when Redis unavailable). Dialogue history is not part of the core indexing path.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlite3` | stdlib | SQLite access | stdlib, no install, same DB as Phase 11/12/13 |
| `numpy` | already in deps | BLOB serialization | `ndarray.tobytes()` / `frombuffer()` is canonical |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `hashlib` | stdlib | `content_hash` computation | Already used in `CacheManager._generate_key()` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ndarray.tobytes()` + `frombuffer()` | `pickle.dumps()` | pickle is larger, not guaranteed stable across numpy versions; BLOB bytes is explicit |
| Inline DDL in embedder.py | Add to `db.py` `_DDL` | db.py is canonical schema location; consistent with Phase 11 pattern |

## Architecture Patterns

### Pattern 1: BLOB round-trip for numpy arrays
**What:** Store float32 embedding as raw bytes; retrieve and reshape
**When to use:** Compact storage; fast serialization; numpy-native
**Example:**
```python
# Store
blob = embedding.astype(np.float32).tobytes()
conn.execute(
    "INSERT OR IGNORE INTO embedding_cache (content_hash, model, embedding) VALUES (?,?,?)",
    (content_hash, model_name, blob)
)

# Retrieve
row = conn.execute(
    "SELECT embedding FROM embedding_cache WHERE content_hash=? AND model=?",
    (content_hash, model_name)
).fetchone()
if row:
    cached = np.frombuffer(row[0], dtype=np.float32)
    if cached.shape[0] != self.embedding_dim:
        raise ValueError(
            f"Cached embedding dim {cached.shape[0]} != expected {self.embedding_dim}. "
            f"Delete embedding_cache (fastcode index --clear-cache) after changing models."
        )
    return cached
```

### Pattern 2: content_hash computation
**What:** Hash the text input to generate a stable cache key
**Example:**
```python
import hashlib
content_hash = hashlib.sha256(text.encode()).hexdigest()
```

**Important:** `embed_text()` takes `text: str` — the hash is computed from text only.
The `model_name` is the second key component (from `self.model_name`).

### Pattern 3: Passing DB connection to CodeEmbedder
**What:** Optional connection parameter; None = no-cache mode
**Example:**
```python
class CodeEmbedder:
    def __init__(self, config, db_conn=None):
        ...
        self._db_conn = db_conn  # None = cache disabled
```

In `main.py`, after `init_db()`:
```python
self.embedder = CodeEmbedder(self.config, db_conn=conn)
```

### Pattern 4: `--clear-cache` in index command
```python
@cli.command()
@click.option('--clear-cache', is_flag=True, help='Clear embedding cache before indexing')
def index(repo_url, repo_path, repo_zip, config, clear_cache):
    fastcode = FastCode(config_path=config)
    if clear_cache:
        # Access DB connection and truncate
        fastcode.db_conn.execute("DELETE FROM embedding_cache")
        fastcode.db_conn.commit()
    fastcode.index_repository()
```

### Schema DDL addition to db.py

```sql
CREATE TABLE IF NOT EXISTS embedding_cache (
    content_hash TEXT NOT NULL,
    model        TEXT NOT NULL,
    embedding    BLOB NOT NULL,
    PRIMARY KEY (content_hash, model)
);
```

Added to `_DDL` string in `fastcode/db.py` alongside existing tables.

### Anti-Patterns to Avoid
- **Caching in `embed_batch()`:** Batch is the API call unit; cache should be per-text in `embed_text()`
- **Storing embeddings as JSON array:** Float32 bytes are 4x smaller and faster to deserialize
- **Silently re-embedding on shape mismatch:** Per CONTEXT.md, raise an error — this surfaces model-switch bugs early

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| BLOB serialization | Custom float encoding | `numpy.ndarray.tobytes()` | stdlib-grade, exact round-trip |
| Content hash | Custom rolling hash | `hashlib.sha256` | Collision-resistant, stdlib |
| Thread safety | Locking | Single-threaded assumption | CLI tool; sqlite3 default behavior fine |

## Common Pitfalls

### Pitfall 1: Forgetting `db_conn` is None in no-cache contexts
**What goes wrong:** Tests that instantiate `CodeEmbedder(config)` without a DB will crash when `embed_text()` tries to query
**Why it happens:** Guard clause missing on `_db_conn`
**How to avoid:** `if self._db_conn is None: skip cache path`

### Pitfall 2: `content_hash` column name collision
**What goes wrong:** `chunks` table already has a `content_hash` column; confusing but separate
**Why it happens:** Same column name in different tables
**How to avoid:** The `embedding_cache` table is independent — no joins needed; clarify in DDL comment

### Pitfall 3: Not committing after INSERT
**What goes wrong:** Cache entries written but not persisted between restarts
**Why it happens:** sqlite3 autocommit is off by default in Python
**How to avoid:** Call `conn.commit()` after each `INSERT` or use `conn.execute("BEGIN")` / `commit()` explicitly

### Pitfall 4: `embed_text()` vs `embed_batch()` cache location
**What goes wrong:** Adding cache to `embed_batch()` misses the `embed_text()` case (batch size = 1)
**Why it happens:** Misreading the call chain
**How to avoid:** Cache goes in `embed_text()` only; it calls `embed_batch()` when cache misses

### Pitfall 5: `CacheManager.get_embedding()` / `set_embedding()` are dead code
**What goes wrong:** Planner tries to "wire up" existing CacheManager embedding methods to CodeEmbedder
**Why it happens:** Assuming existing methods are used
**How to avoid:** These methods are never called; ignore them; add direct SQLite path to `embed_text()`

## Code Examples

### Complete embed_text() with SQLite cache
```python
import hashlib
import sqlite3
import numpy as np

def embed_text(self, text: str, task_type: str = "RETRIEVAL_QUERY") -> np.ndarray:
    if self._db_conn is not None:
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        row = self._db_conn.execute(
            "SELECT embedding FROM embedding_cache WHERE content_hash=? AND model=?",
            (content_hash, self.model_name),
        ).fetchone()
        if row is not None:
            cached = np.frombuffer(row[0], dtype=np.float32)
            if cached.shape[0] != self.embedding_dim:
                raise ValueError(
                    f"Cached embedding dim {cached.shape[0]} != expected {self.embedding_dim}. "
                    f"Run: fastcode index --clear-cache to rebuild."
                )
            return cached

    result = self.embed_batch([text], task_type=task_type)[0]

    if self._db_conn is not None:
        self._db_conn.execute(
            "INSERT OR IGNORE INTO embedding_cache (content_hash, model, embedding) VALUES (?,?,?)",
            (content_hash, self.model_name, result.astype(np.float32).tobytes()),
        )
        self._db_conn.commit()

    return result
```

### Schema DDL fragment
```sql
CREATE TABLE IF NOT EXISTS embedding_cache (
    content_hash TEXT NOT NULL,
    model        TEXT NOT NULL,
    embedding    BLOB NOT NULL,
    PRIMARY KEY (content_hash, model)
);
```

## Open Questions

1. **`CacheManager` and `diskcache` removal**
   - What we know: `CacheManager` uses `DiskCache` for dialogue history (NOT embeddings); the locked decision says "no remaining callers"
   - What's unclear: Whether Phase 14 is expected to remove `CacheManager`'s disk backend too
   - Recommendation: Planner should explicitly address this. Safest approach: remove `diskcache` from `pyproject.toml` AND remove the `disk` backend from `CacheManager._initialize_cache()` — defaulting to Redis-only or in-memory dialogue history. This keeps the locked decision intact without breaking `CacheManager`'s interface.

2. **DB connection exposure in `FastCode` class**
   - What we know: `main.py` instantiates `FastCode`, which creates `CodeEmbedder`; the DB conn lives inside `FastCode`
   - What's unclear: Whether `FastCode._db_conn` exists or needs to be added
   - Recommendation: Check `main.py` for DB init path; add `db_conn` attribute to `FastCode.__init__()` if needed

## Sources

### Primary (HIGH confidence)
- Codebase direct inspection: `fastcode/embedder.py`, `fastcode/cache.py`, `fastcode/db.py`, `main.py`
- Python docs: `sqlite3` BLOB storage, `numpy.ndarray.tobytes()` — stdlib, version-stable

### Secondary (MEDIUM confidence)
- Pattern: numpy BLOB round-trip — common pattern in SQLite-backed vector stores

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib only, no new deps
- Architecture: HIGH — direct codebase inspection
- Pitfalls: HIGH — identified from code review, not assumptions

**Research date:** 2026-03-02
**Valid until:** N/A (internal codebase findings, not time-sensitive)

---

## RESEARCH COMPLETE

**Phase:** 14 - Embedding Cache Migration
**Confidence:** HIGH

### Key Findings
- `CodeEmbedder` does NOT currently use `CacheManager` or `diskcache` — the embedding cache is being added fresh, not migrated
- Only one diskcache caller in the project: `fastcode/cache.py` line 13 (DiskCache import) and line 46 (instantiation)
- `CacheManager` uses diskcache for dialogue history — this is the critical scope issue the planner must resolve
- BLOB round-trip via `numpy.ndarray.tobytes()` / `numpy.frombuffer()` is the correct approach (no new deps)
- Cache entry point: `embed_text()` (not `embed_batch()`) per locked decision; guard on `_db_conn is None` for backward compat
- DiskCache default directory: `./data/cache` (from `cache.py` line with `cache_directory` config key)

### File Created
`.planning/phases/14-embedding-cache-migration/14-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | stdlib only (sqlite3, hashlib, numpy) |
| Architecture | HIGH | Direct codebase inspection |
| Pitfalls | HIGH | Identified from actual code paths |

### Open Questions
- Whether `CacheManager`'s `diskcache` backend is in-scope for removal (planner must decide)
- Whether `FastCode` class already exposes `db_conn` attribute to pass to `CodeEmbedder`

### Ready for Planning
Research complete. Planner can now create PLAN.md files.
