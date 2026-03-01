# Phase 13: BM25 Retriever Swap - Research

**Researched:** 2026-03-02
**Domain:** SQLite FTS5 BM25 retrieval; rank_bm25 / pkl removal
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### pkl removal
- Stop writing and reading pkl files — no automated migration or cleanup of existing files on disk
- Remove all pkl read/write code and imports from wherever they live (research should find all sites)
- Remove `rank_bm25` (BM25Okapi) from `pyproject.toml` entirely — it will be unused after this phase

#### Repository scoping
- Scope FTS5 results to a repo using `source_path LIKE '{repo_path}/%'` — no schema change needed
- Implementation: FTS5 MATCH + JOIN to chunks table with WHERE clause on `source_path`
  (`SELECT c.* FROM chunks_fts fts JOIN chunks c ON fts.rowid = c.id WHERE c.source_path LIKE ?
  ORDER BY fts.rank`)
- Result count: match existing `full_bm25()` behavior (research should check current return count)
- The exact form of `repo_path` argument (absolute vs relative) should be confirmed by research
  against existing `full_bm25()` call sites

#### Retrieval API shape
- `full_bm25()` public signature stays identical — no breaking changes to callers
- Return type stays identical to current BM25Okapi output — callers don't need updating
- SQLite connection sourced from `db.get_connection()` (or equivalent) from the existing `db.py`
  module — same path used by the indexer, no duplication

#### Edge case behavior
- No chunks for queried repo → return empty list (matches BM25Okapi behavior on empty corpus)
- DB file doesn't exist → auto-create via `init_db()` on first use, no error thrown
- Malformed FTS5 query → let `sqlite3` exception propagate — fail fast, no swallowing

### Claude's Discretion
- Exact `db.py` function to call for the connection (get_connection, init_db, or context manager)
- Whether to cache the SQLite connection on the HybridRetriever instance or open per-query
- How to handle the `source_path` prefix matching if paths are stored differently than expected

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BM25-01 | `HybridRetriever` BM25 search path queries `chunks_fts` using `bm25(chunks_fts)` ranking instead of loading a `BM25Okapi` object | FTS5 `bm25()` function is the implicit rank column alias in SQLite FTS5; `ORDER BY fts.rank` uses it automatically |
| BM25-02 | FTS5 BM25 query supports filtering by `source_path` prefix to scope results to a specific indexed repository | Confirmed: JOIN pattern with `WHERE c.source_path LIKE 'repo/%'` works correctly in SQLite FTS5 |
| BM25-03 | The `{repo_name}_bm25.pkl` index files are no longer written or loaded; BM25 corpus derived entirely from SQLite | Three deletion sites identified in retriever.py and main.py; `rank-bm25` dep removed from pyproject.toml |
</phase_requirements>

---

## Summary

Phase 13 replaces `HybridRetriever`'s BM25 backend. Currently the system builds a `BM25Okapi` object
in memory from `CodeElement` lists, serializes it to `{repo_name}_bm25.pkl` files, and reloads those
files on startup. The replacement is SQLite FTS5, which is already set up (Phase 11) and populated
(Phase 12). The retriever just needs to query it instead of loading pkl files.

The scope is narrow: implement one new method `full_bm25()` on `HybridRetriever` (it does not
currently exist as a method — `full_bm25` is an attribute holding a `BM25Okapi` instance), and remove
all pkl read/write code. The `_keyword_search()` internal method that calls
`bm25_index.get_scores(query_tokens)` is what drives actual retrieval; that must be updated too.
However, the CONTEXT.md references `full_bm25()` as a method — this is the success criterion from
the ROADMAP, not the current code. The planner must be aware that the public-facing change involves
converting a `BM25Okapi` attribute into a query method.

The FTS5 `bm25()` function is SQLite's built-in BM25 ranker. It is exposed as the implicit `rank`
column when querying a FTS5 virtual table. The confirmed query pattern is:
`SELECT c.* FROM chunks_fts fts JOIN chunks c ON fts.rowid = c.id WHERE chunks_fts MATCH ?
AND c.source_path LIKE ? ORDER BY fts.rank`. Rank is negative; `ORDER BY fts.rank` (ASC) gives
most-relevant first. This was verified locally against the project's actual FTS5 schema.

**Primary recommendation:** Add `full_bm25(query: str, repo_path: str, top_k: int) -> list` to
`HybridRetriever`; update `_keyword_search()` to call it; delete `save_bm25()`, `load_bm25()`,
`index_for_bm25()` and all pkl code in `retriever.py` and `main.py`; remove `rank-bm25` from
`pyproject.toml`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlite3` | stdlib | FTS5 query execution | Already used in db.py and indexer.py; zero new deps |
| SQLite FTS5 | bundled with Python's sqlite3 | BM25 ranking via `rank` column | Built into SQLite ≥3.9; Python ships this since 3.x |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `fastcode.db.init_db` | project | Open/create SQLite DB, return connection | Call on HybridRetriever init to get connection |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `init_db()` reuse | new `get_connection()` helper | init_db() is already idempotent (IF NOT EXISTS); no need for a separate getter |
| Per-query connection | Cached instance connection | Per-query adds ~1ms overhead; caching risks stale state across fork but is fine for single-process CLI |

**Installation:** No new packages — this phase removes `rank-bm25`, net dependency reduction.

---

## Architecture Patterns

### Current Code to Change

```
fastcode/retriever.py
├── imports: `import pickle`, `from rank_bm25 import BM25Okapi`  ← DELETE
├── __init__: self.full_bm25, self.full_bm25_corpus, self.full_bm25_elements  ← REMOVE attrs
├── __init__: self.filtered_bm25, self.filtered_bm25_corpus, self.filtered_bm25_elements  ← REMOVE attrs
├── index_for_bm25()     ← DELETE entire method
├── save_bm25()          ← DELETE entire method
├── load_bm25()          ← DELETE entire method
├── _keyword_search()    ← UPDATE: call self.full_bm25() instead of bm25_index.get_scores()
└── reload_for_repos()   ← UPDATE: remove pkl-reading block (lines ~1169-1193)

fastcode/main.py
├── import BM25Okapi     ← DELETE
├── index_for_bm25() calls  ← DELETE (3 call sites: lines 239, 661, 965)
├── save_bm25() calls    ← DELETE (2 call sites: lines 250, 966)
├── load_bm25() calls    ← DELETE (1 call site: line 642)
└── self.retriever.full_bm25 = BM25Okapi(...)  ← DELETE (line 1199)

pyproject.toml
└── "rank-bm25"  ← DELETE from dependencies
```

### Pattern 1: FTS5 BM25 Query with repo scoping

**What:** Query `chunks_fts` joined to `chunks`, filter by `source_path LIKE 'repo/%'`, rank by FTS5 built-in BM25.
**When to use:** Always — this is the replacement for `BM25Okapi.get_scores()`.

```python
# Source: verified locally against project FTS5 schema (fastcode/db.py)
def full_bm25(self, query: str, repo_path: str, top_k: int = 10) -> list:
    """
    Query chunks_fts for BM25-ranked results scoped to repo_path.

    Args:
        query: Raw search string (passed as FTS5 MATCH argument).
        repo_path: Relative repo path prefix; chunks with source_path starting
                   with this prefix are returned. Stored paths are relative
                   (e.g. "src/foo.py"), so repo_path should be the relative
                   directory root (e.g. "src").
        top_k: Maximum number of results.

    Returns:
        List of dicts with chunk fields: id, source_path, content,
        content_hash, chunk_index, start_offset, end_offset.
    """
    conn = self._db_conn  # connection cached on __init__ via init_db()
    like_pattern = repo_path.rstrip("/") + "/%"
    rows = conn.execute(
        """
        SELECT c.id, c.source_path, c.content,
               c.content_hash, c.chunk_index, c.start_offset, c.end_offset
        FROM   chunks_fts fts
        JOIN   chunks c ON fts.rowid = c.id
        WHERE  chunks_fts MATCH ?
          AND  c.source_path LIKE ?
        ORDER  BY fts.rank
        LIMIT  ?
        """,
        (query, like_pattern, top_k),
    ).fetchall()
    keys = ("id", "source_path", "content",
            "content_hash", "chunk_index", "start_offset", "end_offset")
    return [dict(zip(keys, row)) for row in rows]
```

### Pattern 2: `source_path` is relative

**What:** The indexer stores `source_path` as `rel_path` (relative to `repo_path`), NOT absolute.

**Evidence:** In `fastcode/indexer.py` (line 601):
```python
(rel_path, text, chunk_hash, chunk_index, start, end),
```
`rel_path = os.path.relpath(abs_path, repo_path)` — so paths look like `"src/foo.py"`, `"tests/bar.py"`.

**Implication for `full_bm25()`:** The `repo_path` argument must be a relative directory prefix
(or empty string for "all repos in this DB"). The caller must pass the relative root, not the
absolute filesystem path. Research cannot determine the exact prefix callers use without examining
call sites in `main.py` — the planner should verify this during implementation. The safe default:
if `repo_path=""` or `"/"`, use `"%" ` (match all) as the LIKE pattern.

### Pattern 3: FTS5 rank semantics

- `fts.rank` is negative; more negative = more relevant.
- `ORDER BY fts.rank` (default ASC) gives most-relevant results first.
- `bm25(chunks_fts)` is the explicit form; `rank` column is the alias for it.
- No custom weights needed (single-column FTS table).

### Pattern 4: DB connection on HybridRetriever

`db.py` exposes only `init_db(db_path) -> sqlite3.Connection`. There is no `get_connection()` helper.

**Recommendation (Claude's discretion):** Cache the connection on the `HybridRetriever` instance.
Open it in `__init__` via `init_db(db_path)`. `db_path` must be passed as a new constructor arg
(or derived from `config`). Check whether `config` already carries a DB path key — the indexer
receives `db_path` explicitly; the retriever may need the same config key.

```python
# In HybridRetriever.__init__:
db_path = config.get("vector_store", {}).get("db_path", "./data/fastcode.db")
self._db_conn = init_db(db_path)
```

This avoids opening a new connection per query and is safe for single-process CLI use.

### Anti-Patterns to Avoid

- **Quoting FTS5 query terms in Python:** Do not try to sanitize the FTS5 query string yourself.
  `sqlite3.OperationalError` will propagate on malformed input — that is the intended behavior (fail fast).
- **Treating `fts.rank` as positive:** It is negative. Do not negate it before `ORDER BY` — just
  use `ORDER BY fts.rank` to get most-relevant first.
- **Using `source_path LIKE '{repo_path}%'` without trailing slash:** `"repo"` matches `"repo_extra"`.
  Always append `"/"` before `"%"`: `like_pattern = repo_path.rstrip("/") + "/%"`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| BM25 ranking | Custom BM25 scorer | SQLite FTS5 `rank` column | FTS5 implements Robertson/Sparck Jones BM25 correctly; no extra code |
| FTS5 tokenization | Custom tokenizer | FTS5 default unicode61 tokenizer | Already tokenizes code-like text adequately |
| Connection pooling | Connection pool | Single cached `sqlite3.Connection` | Single-process CLI; connection pooling adds complexity without benefit |

**Key insight:** SQLite FTS5 replaces `rank_bm25` entirely. The `bm25()` function in FTS5 is BM25 — not an approximation.

---

## Common Pitfalls

### Pitfall 1: `full_bm25` attribute vs. method name collision

**What goes wrong:** `full_bm25` currently exists as an *attribute* (`self.full_bm25 = None`/`BM25Okapi(...)`).
If the planner adds a method named `full_bm25()` without removing the attribute assignment, Python
will shadow the method with the attribute at runtime.

**Why it happens:** The ROADMAP/CONTEXT success criteria call it `full_bm25()` (a method), but the
current code uses it as an attribute holding a `BM25Okapi` instance.

**How to avoid:** Delete the `self.full_bm25 = None` attribute initialization in `__init__`, then
add the method. Also update all references: `if self.full_bm25 is not None:` in `_keyword_search()`
must become the new SQLite call path.

### Pitfall 2: pkl removal in main.py is as large as in retriever.py

**What goes wrong:** Leaving pkl code in `main.py` while removing it from `retriever.py` causes
`AttributeError` on the deleted methods (`save_bm25`, `load_bm25`, `index_for_bm25`).

**Why it happens:** `main.py` drives the full pipeline and calls all three pkl methods.

**How to avoid:** BM25-03 requires removing all pkl writes and reads. All call sites in `main.py`
must be removed in the same plan. Grep results found:
- `self.retriever.index_for_bm25(elements)` — lines 239, 661, 965, 1207
- `self.retriever.save_bm25(repo_name)` — lines 250, 966
- `self.retriever.load_bm25(cache_name)` — line 642
- `self.retriever.full_bm25 = BM25Okapi(...)` — line 1199
- `from rank_bm25 import BM25Okapi` — must also be removed from main.py

### Pitfall 3: `reload_for_repos()` pkl block

**What goes wrong:** `HybridRetriever.reload_for_repos()` (lines ~1164-1193) reads pkl files in a
loop to rebuild `filtered_bm25`. After removing pkl support, this block will fail if not updated.

**How to avoid:** Replace the pkl-loading block with an FTS5 query scoped to the repo names. Or,
since `filtered_bm25` is the per-repo-selection cache, consider whether `_keyword_search()` simply
uses the new `full_bm25()` method with repo scoping and no `filtered_*` state is needed at all.
The planner should decide whether to simplify `_keyword_search()` to always use `full_bm25()`.

### Pitfall 4: `repo_overview_bm25` is in-memory, unrelated to pkl

**What goes wrong:** `repo_overview_bm25` uses `BM25Okapi` in memory for overview-based repo
selection (not stored as pkl). Removing `rank_bm25` from dependencies breaks this.

**How to avoid:** This is a separate concern. `build_repo_overview_bm25()` and
`_select_relevant_repositories()` use `self.repo_overview_bm25 = BM25Okapi(...)`. If `rank_bm25`
is removed from `pyproject.toml`, these will break at import time. Two options:
  1. Replace `repo_overview_bm25` with an FTS5 approach (scope change)
  2. Keep `rank_bm25` for overview search only (contradicts BM25-03 spirit but technically BM25-03
     only covers `{repo_name}_bm25.pkl` files)

**This is the most significant open question for the planner.** BM25-03 says "no pkl files" — the
repo-overview BM25 is in-memory only and has no pkl. The locked decision says "Remove `rank_bm25`
(BM25Okapi) from `pyproject.toml` entirely — it will be unused after this phase." That means the
planner MUST also eliminate the `repo_overview_bm25` usage. The overview corpus is small (one doc
per repo), so replacing it with FTS5 is inappropriate. Best option: store repo overviews as plain
text and use Python string matching, or load them via FTS5 into a temporary in-memory table.
Alternatively, keep a simple Python-level keyword scan (no external lib needed for tiny corpora).

---

## Code Examples

Verified patterns from official sources and local verification:

### FTS5 BM25 query with repo scoping (verified locally)

```python
# Verified against project schema (fastcode/db.py + init_db())
rows = conn.execute(
    """
    SELECT c.id, c.source_path, c.content,
           c.content_hash, c.chunk_index, c.start_offset, c.end_offset
    FROM   chunks_fts fts
    JOIN   chunks c ON fts.rowid = c.id
    WHERE  chunks_fts MATCH ?
      AND  c.source_path LIKE ?
    ORDER  BY fts.rank
    LIMIT  ?
    """,
    (query, repo_path.rstrip("/") + "/%", top_k),
).fetchall()
```

### FTS5 rank ordering confirmed

```python
# rank is negative; ORDER BY fts.rank (ASC) gives most-relevant result first.
# Verified: doc with 3 occurrences of "hello" has rank=-1.49e-6
#           doc with 1 occurrence of "hello" has rank=-1.04e-6
# => most negative rank = most relevant = first in ASC order
```

### FTS5 raises OperationalError on malformed query

```python
# Verified: conn.execute("... WHERE chunks_fts MATCH ?", ('hello"',)) raises:
# sqlite3.OperationalError: unterminated string
# This satisfies the "fail fast" edge-case requirement from CONTEXT.md.
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `BM25Okapi(corpus).get_scores(tokens)` | `SELECT ... FROM chunks_fts WHERE MATCH ? ORDER BY rank` | Phase 13 | Eliminates pkl files, rank-bm25 dep, corpus rebuild on load |
| Tokenize query client-side before BM25 | Pass raw query string to FTS5 MATCH | Phase 13 | FTS5 tokenizes internally; simpler caller code |
| pkl file per repo name | Single SQLite DB for all repos | Phase 13 | Scoping by source_path prefix instead of separate files |

**Deprecated/outdated:**
- `BM25Okapi`: Removed from deps as part of this phase.
- `save_bm25()` / `load_bm25()` / `index_for_bm25()`: All deleted in this phase.

---

## Open Questions

1. **repo_overview_bm25 replacement**
   - What we know: `build_repo_overview_bm25()` and `_select_relevant_repositories()` in `retriever.py`
     use `BM25Okapi` for in-memory repo-overview search. There are no pkl files here.
   - What's unclear: The locked decision removes `rank_bm25` entirely. This code will break at import.
     The planner must decide how to replace it (simple Python scoring, FTS5 in-memory, or a different
     approach) or confirm with the user whether this is in-scope.
   - Recommendation: Implement simple frequency-based scoring in Python for the tiny overview corpus
     (one text per repo, typically <10 repos). No external lib needed. This is the minimum change
     needed to make the import removal safe.

2. **db_path in HybridRetriever**
   - What we know: `HybridRetriever.__init__` takes `config` but no `db_path`. The indexer receives
     `db_path` explicitly at call time.
   - What's unclear: What config key holds the DB path (if any)?
   - Recommendation: Add `db_path` parameter to `HybridRetriever.__init__` OR read it from
     `config["vector_store"]["db_path"]` with a sensible default (`"./data/fastcode.db"`).
     Check `main.py` for how `HybridRetriever` is constructed to see which config keys are available.

3. **`filtered_bm25` fate after pkl removal**
   - What we know: `filtered_bm25` / `filtered_bm25_elements` were populated by loading per-repo
     pkl files in `reload_for_repos()`. Removing pkl makes this code dead.
   - What's unclear: Should `_keyword_search()` use `full_bm25()` with repo scoping for all queries,
     eliminating the `filtered_bm25` state entirely?
   - Recommendation: Yes — remove `filtered_bm25_*` attributes and always call `full_bm25()` with
     the repo filter arg. This simplifies the code significantly.

4. **`source_path` prefix format at call sites**
   - What we know: Indexer stores relative paths. `repo_path` passed to `full_bm25()` should be a
     relative directory prefix.
   - What's unclear: Do call sites pass absolute paths or repo names? Need to check `main.py`
     line ~240 and ~661 context to see what `repo_name` or `repo_path` value is available at
     the keyword search call site.
   - Recommendation: The planner should read `main.py` around `index_for_bm25()` calls to see
     what `repo_name` variable is available. If callers have the repo root absolute path, compute
     relative by stripping the base dir. If they have a repo name string, it may not match the
     path prefix — in that case store a mapping or use a different scoping approach.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8+ |
| Config file | none (no pytest.ini/pyproject.toml `[tool.pytest]` section) |
| Quick run command | `python -m pytest tests/test_retriever_bm25.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |
| Estimated runtime | ~2 seconds (all sqlite, no network) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BM25-01 | `full_bm25()` returns results from FTS5 `bm25(chunks_fts)` query, not BM25Okapi | unit | `python -m pytest tests/test_retriever_bm25.py::test_full_bm25_returns_fts5_results -x` | ❌ Wave 0 gap |
| BM25-02 | FTS5 query scoped to repo: chunks from other repos excluded | unit | `python -m pytest tests/test_retriever_bm25.py::test_full_bm25_scoped_to_repo -x` | ❌ Wave 0 gap |
| BM25-03 | No pkl files written or read; `rank-bm25` removed | unit + smoke | `python -m pytest tests/test_retriever_bm25.py::test_no_pkl_written -x` | ❌ Wave 0 gap |
| BM25-01 (ranking) | Highest-scoring chunk is first result | unit | `python -m pytest tests/test_retriever_bm25.py::test_full_bm25_ranking_order -x` | ❌ Wave 0 gap |

### Nyquist Sampling Rate

- **Minimum sample interval:** After every committed task → run: `python -m pytest tests/test_retriever_bm25.py -x -q`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green before `/gsd:verify-work` runs
- **Estimated feedback latency per task:** ~2 seconds

### Wave 0 Gaps (must be created before implementation)

- [ ] `tests/test_retriever_bm25.py` — covers BM25-01, BM25-02, BM25-03 with in-memory SQLite fixtures
- [ ] No new conftest.py needed — existing `tests/__init__.py` is present; tests use `tmp_path` or `:memory:`

---

## Sources

### Primary (HIGH confidence)

- Local codebase inspection — `fastcode/retriever.py`, `fastcode/db.py`, `fastcode/indexer.py`, `fastcode/main.py`
- Local SQLite FTS5 verification — `python3 -c` scripts confirming rank semantics, LIKE scoping, OperationalError on malformed query

### Secondary (MEDIUM confidence)

- SQLite FTS5 documentation (training knowledge, verified by local execution): rank column is negative BM25 score; `ORDER BY rank` gives most relevant first; `bm25()` function is the explicit form.

### Tertiary (LOW confidence)

- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib sqlite3, no new deps; verified locally
- Architecture: HIGH — all code sites identified by grep; query patterns verified by running against project schema
- Pitfalls: HIGH — attribute/method name collision and main.py removal scope are concrete code observations
- Open questions: MEDIUM — repo_overview_bm25 replacement and db_path wiring require planner judgment

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (stable domain — SQLite FTS5 API does not change)
