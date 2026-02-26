---
phase: 07-dependency-cleanup-and-smoke-test
verified: 2026-02-25T10:30:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
---

# Phase 7: Dependency Cleanup and Smoke Test — Verification Report

**Phase Goal:** Remove sentence-transformers from the dependency tree, clean up Dockerfile and main.py, add a smoke test that validates embedding via ADC.
**Verified:** 2026-02-25T10:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `pip install -r requirements.txt` does not install sentence-transformers or torch | VERIFIED | `requirements.txt` has no `sentence-transformers` line; `faiss-cpu` and all other dependencies intact. `grep` returns exit 1. |
| 2 | A config-absent deploy defaults CodeEmbedder to `vertex_ai/gemini-embedding-001`, not a sentence-transformers string | VERIFIED | `main.py` line 848: `"model": "vertex_ai/gemini-embedding-001"`, line 849: `"embedding_dim": 3072`, line 851: `"normalize_embeddings": True`. No `device` key present. |
| 3 | docker build completes without downloading any embedding model | VERIFIED | Dockerfile contains no `RUN python -c "from sentence_transformers..."` layer. Comment on COPY line reads "# Copy application code". Grep for `SentenceTransformer|sentence_transformers|pre-bake|pre-download` returns no matches. |
| 4 | No remaining `sentence-transformers/` strings in `fastcode/` source files | VERIFIED | `grep -rn "sentence-transformers/" fastcode/ --include="*.py"` returns exit 1. (Note in SUMMARY: a stale `.pyc` binary matched; confirmed `.py` sources are clean — `.pyc` is a pre-existing cache artifact.) |
| 5 | Smoke test skips cleanly in CI when `VERTEXAI_PROJECT` is unset | VERIFIED | Live run with `.env` present: `1 passed` in 14s. Structural check confirms `@pytest.mark.skipif(not os.environ.get("VERTEXAI_PROJECT"), reason="VERTEXAI_PROJECT not set — skipping live test")` is present. |
| 6 | Smoke test passes with real GCP credentials by calling `embed_text()` end-to-end | VERIFIED | `python3 -m pytest tests/test_embedder_smoke.py -v` returned `1 passed`. SUMMARY documents live pass: "Verified end-to-end: embed_text('hello world', task_type='RETRIEVAL_QUERY') returned a (3072,) ndarray with all finite values and L2 norm of 1.0". |
| 7 | Smoke test asserts ndarray shape (3072,), all finite, L2 norm approximately 1.0 | VERIFIED | Lines 36-40 of `tests/test_embedder_smoke.py`: `assert isinstance(result, np.ndarray)`, `assert result.shape == (3072,)`, `assert np.all(np.isfinite(result))`, `assert abs(norm - 1.0) < 1e-5`. |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact | Expected | Level 1: Exists | Level 2: Substantive | Level 3: Wired | Status |
|----------|----------|-----------------|----------------------|----------------|--------|
| `requirements.txt` | Dependency list with sentence-transformers removed; contains `faiss-cpu` | Yes | `faiss-cpu` present at line 23; no `sentence-transformers` line in 58-line file | Read by `pip install` at build time | VERIFIED |
| `fastcode/main.py` | Default config returning `vertex_ai/gemini-embedding-001` | Yes | Lines 847-852: full embedding block with `vertex_ai/gemini-embedding-001`, `embedding_dim: 3072`, `normalize_embeddings: True`, no `device` key | `embedder.py CodeEmbedder.__init__()` reads `config.get("embedding", {})` at line 17-23 | VERIFIED |
| `Dockerfile` | Build file without pre-bake RUN layer | Yes | 34-line file; no `SentenceTransformer` or `sentence_transformers` reference; COPY comment reads "# Copy application code" | Used by `docker build` at deploy time | VERIFIED |
| `tests/test_embedder_smoke.py` | Embedding smoke test exercising CodeEmbedder via litellm + ADC | Yes | 40 lines (exceeds min 30); class `TestEmbedderSmoke` with skipif guard, 4 assertions, no try/except, no hardcoded project ID | `CodeEmbedder` imported inside test method; calls `embed_text()` | VERIFIED |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `fastcode/main.py _get_default_config()` | `fastcode/embedder.py CodeEmbedder.__init__()` | `config['embedding']['model']` read at init | WIRED | `embedder.py` line 20: `self.model_name = self.embedding_config.get("model", "vertex_ai/gemini-embedding-001")`. `embedding_dim` (line 23), `normalize_embeddings` (line 22), `batch_size` (line 21) all read. |
| `requirements.txt` | pip install | absence of `sentence-transformers` line | WIRED | File confirmed clean of `sentence-transformers`. `faiss-cpu` and `litellm[google]` present. |
| `tests/test_embedder_smoke.py TestEmbedderSmoke` | `fastcode.embedder.CodeEmbedder.embed_text()` | direct import and call with `task_type=RETRIEVAL_QUERY` | WIRED | Line 23: `from fastcode.embedder import CodeEmbedder`. Line 34: `embedder.embed_text("hello world", task_type="RETRIEVAL_QUERY")`. |
| `fastcode.embedder.CodeEmbedder.embed_text()` | `litellm.embedding() → VertexAI gemini-embedding-001` | litellm routing via `vertex_ai/` prefix + ADC | WIRED | `embedder.py` line 64: `litellm.embedding(model=self.model_name, ...)`. Live test PASSED (14s round-trip confirms ADC path active). |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| R8 | 07-01-PLAN.md | Remove `sentence-transformers` from `requirements.txt` | SATISFIED | Line deleted; grep returns exit 1; committed in `6ccda4d` |
| R9 | 07-01-PLAN.md | Remove Dockerfile pre-bake `SentenceTransformer(...)` RUN layer | SATISFIED | Three-line block removed; COPY comment updated; committed in `8e22591` |
| R10 | 07-01-PLAN.md | Update `main.py` default string to `vertex_ai/gemini-embedding-001` | SATISFIED | `_get_default_config()` embedding block lines 847-852 contain correct keys; committed atomically with R8 in `6ccda4d` |
| R11 | 07-02-PLAN.md | Add embedding smoke test via ADC with skipif guard | SATISFIED | `tests/test_embedder_smoke.py` exists (40 lines), passes live, committed in `e4b69b4` |

**Orphaned requirements check:** REQUIREMENTS.md R8, R9, R10, R11 are all claimed by phase 07 plans. No orphaned requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `fastcode/main.py` | 1194 | `# TODO: Merge additional repository graphs if needed` | Info | Pre-existing comment in unrelated code path (multi-repo graph merge). Not introduced by phase 07. No impact on phase goal. |

---

### Human Verification Required

None. All observable truths were fully verifiable programmatically:

- `requirements.txt` and `Dockerfile` are text files — fully greppable.
- `main.py` default config block was read directly.
- Smoke test was executed live and returned `1 passed`.

The one item that required live credentials (`VERTEXAI_PROJECT`) was already present in the local `.env` and the test passed.

---

### Gaps Summary

No gaps. All four requirements (R8, R9, R10, R11) are satisfied. All three modified files (`requirements.txt`, `Dockerfile`, `fastcode/main.py`) and the one new file (`tests/test_embedder_smoke.py`) exist with substantive, non-stub content. All key links are wired. The smoke test passed live in the developer environment and the skipif guard is structurally verified.

Commits documented in summaries were confirmed to exist in git history:
- `6ccda4d` — R8 + R10 atomic commit
- `8e22591` — R9 Dockerfile cleanup
- `e4b69b4` — R11 smoke test

---

_Verified: 2026-02-25T10:30:00Z_
_Verifier: Claude (gsd-verifier)_
