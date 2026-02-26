# Phase 7: Dependency Cleanup and Smoke Test — Research

**Researched:** 2026-02-25
**Domain:** Python dependency management, Dockerfile cleanup, pytest smoke test patterns
**Confidence:** HIGH

---

## Summary

Phase 7 is a cleanup and validation pass completing the sentence-transformers removal story started in Phase 6. Phase 6 rewrote the embedder runtime (R1–R7); Phase 7 removes the now-dead dependency artifacts (R8, R9, R10) and adds a live-API smoke test to prove the new path works (R11).

All four changes are small and surgically scoped. The risk profile is low because Phase 6 already verified the code path is correct. The main planning concern is the order-dependency between R10 (update `main.py` default string) and R8 (remove `sentence-transformers` from `requirements.txt`): if R8 lands first and `main.py` still names a `sentence-transformers/...` default, any deploy that does not supply a config file will attempt to instantiate `CodeEmbedder` with a model name that implies a package that is no longer installed. The plan must serialize these as R10-before-R8 or combine them into one commit.

The smoke test (R11) must follow the existing pattern established in `tests/test_vertexai_smoke.py`: class-based, `@pytest.mark.skipif` on `not os.environ.get("VERTEXAI_PROJECT")`, and a concrete assertion against the returned ndarray (shape `(3072,)` and L2 norm ≈ 1.0). No new test infrastructure is needed; pytest is already installed.

**Primary recommendation:** Implement R10 and R8 in a single atomic commit (or R10 strictly before R8), then R9, then R11.

---

<phase_requirements>
## Phase Requirements

| ID  | Description | Research Support |
|-----|-------------|-----------------|
| R8  | Remove `sentence-transformers` from `requirements.txt` line 23 | Single-line deletion; `torch` is not listed explicitly — it arrived transitively via sentence-transformers so no `torch` line to remove. Must be done after or with R10. |
| R9  | Remove Dockerfile pre-bake `RUN python -c "from sentence_transformers..."` line 21 | Single-line deletion. Comment on line 19 ("Pre-download the embedding model...") and line 20 comment context should also be removed or updated; leaving orphaned build comments is confusing. |
| R10 | Update `fastcode/main.py` `_get_default_config()` default embedding block | Replace `"model": "sentence-transformers/all-MiniLM-L6-v2"` and `"device": "cpu"` with `"model": "vertex_ai/gemini-embedding-001"` and `"embedding_dim": 3072`. Remove `"device"` key entirely — it is not a recognized config key in the new CodeEmbedder. |
| R11 | Create `tests/test_embedder_smoke.py` — smoke test via ADC | New file. Follows the pattern in `tests/test_vertexai_smoke.py`. Skips when `VERTEXAI_PROJECT` unset. Asserts ndarray shape `(3072,)`, all finite, norm ≈ 1.0. |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | installed (see requirements.txt) | Test runner for R11 smoke test | Already in project; all existing tests use it |
| litellm | `>=1.80.8[google]` | Embedding call in smoke test | Already dependency; `litellm.embedding()` is the new backend confirmed by Phase 6 |
| numpy | installed | Assertion on ndarray shape and norm | Already dependency; used in embedder.py |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | installed | `load_dotenv()` in smoke test to pick up `.env` credentials | Matches pattern in `tests/test_vertexai_smoke.py` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Class-based test with `skipif` on class | Module-level `pytest.skip()` in `conftest.py` | Class-based `skipif` matches existing project pattern exactly; conftest approach adds indirection with no benefit |
| `pytest.importorskip` | `@pytest.mark.skipif(not os.environ.get(...))` | `importorskip` is for missing packages, not missing env vars; skipif is the correct tool here |

---

## Architecture Patterns

### Current File State (as of Phase 6 completion)

```
requirements.txt line 23:  sentence-transformers           ← R8: delete this line
Dockerfile line 21:         RUN python -c "from sentence_transformers..."   ← R9: delete this line
fastcode/main.py line 848:  "model": "sentence-transformers/all-MiniLM-L6-v2",   ← R10: replace
fastcode/main.py line 849:  "device": "cpu",                ← R10: remove (dead key)
tests/test_embedder_smoke.py: does not exist                ← R11: create
```

### Pattern 1: Existing Smoke Test Pattern (HIGH confidence)

All smoke tests in this project follow the pattern in `tests/test_vertexai_smoke.py`:

```python
# Source: /Users/knakanishi/Repositories/FastCode/tests/test_vertexai_smoke.py
import os
import pytest
from dotenv import load_dotenv

load_dotenv()

class TestEmbedderSmoke:
    @pytest.mark.skipif(
        not os.environ.get("VERTEXAI_PROJECT"),
        reason="VERTEXAI_PROJECT not set — skipping live test",
    )
    def test_happy_path_returns_valid_embedding(self):
        """Call VertexAI embedding via ADC and assert shape and normalization."""
        # ... (see Code Examples section)
```

Key structural elements:
- `load_dotenv()` at module level (not in setup)
- Class-based test class (not bare functions)
- `@pytest.mark.skipif` with `not os.environ.get("VERTEXAI_PROJECT")` guard
- Reason string matches existing test: `"VERTEXAI_PROJECT not set — skipping live test"`

### Pattern 2: main.py `_get_default_config()` embedding block update

Current state (lines 847-851):
```python
"embedding": {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "device": "cpu",
    "batch_size": 32,
},
```

Target state (matching `config/config.yaml` which was updated in Phase 6):
```python
"embedding": {
    "model": "vertex_ai/gemini-embedding-001",
    "embedding_dim": 3072,
    "batch_size": 32,
    "normalize_embeddings": True,
},
```

Note: `normalize_embeddings` should be added to match `config/config.yaml` for consistency. The `device` key must be removed — CodeEmbedder no longer reads it and its presence in defaults is misleading.

### Pattern 3: Dockerfile cleanup

Current lines 19-21:
```dockerfile
# Pre-download the embedding model BEFORE copying app code
# so that code changes don't invalidate this ~470MB cached layer
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"
```

Remove all three lines (the two comments and the RUN instruction). The rationale comment about cache invalidation is also obsolete — there is no model to pre-bake. The Dockerfile has a separate comment on line 26 ("Copy application code (changes here won't re-download the model)") that will also be misleading; update or remove it.

### Anti-Patterns to Avoid

- **R8 before R10:** Removing sentence-transformers from requirements before updating `main.py` defaults creates a window where a config-absent deploy fails with ImportError on startup. Commit R10 first or in the same commit as R8.
- **Leaving orphaned comments in Dockerfile:** Remove the comment block that explains the now-removed pre-bake layer. Orphaned comments mislead maintainers.
- **Adding `device` to new defaults:** The new CodeEmbedder.__init__() does not read `device` from config. Do not carry it forward.
- **Hardcoding `VERTEXAI_PROJECT` in the smoke test:** The smoke test must read the env var, not hardcode a project ID.
- **Calling `litellm.embedding()` directly in the smoke test without going through `CodeEmbedder`:** The test should exercise the full stack (`CodeEmbedder.embed_text()`), not bypass it. This is what R11 requires.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Skipping tests when credentials absent | Custom skip logic or conftest.py fixture | `@pytest.mark.skipif(not os.environ.get("VERTEXAI_PROJECT"), ...)` | Matches existing project pattern; pytest handles skip cleanly |
| Checking L2 norm | Custom loop | `np.linalg.norm(result)` + `abs(norm - 1.0) < 1e-5` | Already used in Phase 6 verification; documented in R11 requirement |

**Key insight:** Everything needed is already in the project. No new packages. No new test infrastructure. Pure cleanup.

---

## Common Pitfalls

### Pitfall 1: Order Dependency — R8 before R10
**What goes wrong:** `requirements.txt` has sentence-transformers removed; `main.py` still defaults to `"sentence-transformers/all-MiniLM-L6-v2"`. Any deploy without a `config.yaml` (or with `config.yaml` missing the embedding section) will call `CodeEmbedder.__init__()` with `self.model_name = "sentence-transformers/all-MiniLM-L6-v2"`. When `embed_text()` is called, `litellm.embedding(model="sentence-transformers/all-MiniLM-L6-v2", ...)` will fail because litellm does not know how to route that string. The failure is a `BadRequestError` or similar, not an ImportError — confusing to diagnose.
**Why it happens:** Two separate files both contain the old model string; Phase 6 only updated `fastcode/embedder.py`'s default, not `main.py`.
**How to avoid:** Commit R10 in the same commit as R8, or strictly before it.
**Warning signs:** `grep -rn "sentence-transformers/" fastcode/` returns hits in `main.py` after Phase 7 commit.

### Pitfall 2: Dead `device` key left in main.py defaults
**What goes wrong:** `"device": "cpu"` remains in `_get_default_config()`. CodeEmbedder no longer reads it, so it is harmless at runtime. However it signals to readers that CPU device selection still applies — wrong mental model.
**How to avoid:** Remove `"device": "cpu"` when updating the embedding block in R10.

### Pitfall 3: Smoke test skips in CI but silently passes elsewhere
**What goes wrong:** A test that always skips is indistinguishable from one that's broken. If `VERTEXAI_PROJECT` is set in the test runner environment, the smoke test must actually make a live call.
**How to avoid:** The test is designed to skip only when the env var is absent. When credentials are present, it must call `embed_text()` and make real assertions. Do not add try/except around the assertion.

### Pitfall 4: Dockerfile TOKENIZERS_PARALLELISM env var
**What goes wrong:** `Dockerfile` line 36 sets `ENV TOKENIZERS_PARALLELISM=false`. After removing sentence-transformers, this env var is no longer meaningful. However, removing it is low-risk (setting a no-op env var harms nothing) and out-of-scope per R9's description which targets only the pre-bake RUN line.
**How to avoid:** Per the requirements, R9 only removes the pre-bake RUN line. Leave `ENV TOKENIZERS_PARALLELISM=false` in place unless the planner explicitly includes it in R9's scope. It is harmless.

### Pitfall 5: fastcode/__init__.py platform import block (deferred item)
**What goes wrong:** `fastcode/__init__.py` lines 7-13 set `TOKENIZERS_PARALLELISM`, `OMP_NUM_THREADS`, etc. via `import platform`. This was deferred in Phase 6. R10 does not require touching `__init__.py`.
**How to avoid:** This is listed in `deferred-items.md` as out of scope for Phase 6. It is also not in Phase 7's R8-R11 scope. Do NOT include it in Phase 7 tasks unless scope is explicitly expanded. It remains dead code but harmless.

---

## Code Examples

### R11: Smoke test file (complete pattern)

```python
# Source: Pattern from tests/test_vertexai_smoke.py; spec from REQUIREMENTS.md R11
"""
Embedder smoke test — validates litellm.embedding() + ADC integration for
fastcode.embedder.CodeEmbedder.

Skips when VERTEXAI_PROJECT is not set (CI without credentials).
"""
import os

import numpy as np
import pytest
from dotenv import load_dotenv

load_dotenv()


class TestEmbedderSmoke:
    @pytest.mark.skipif(
        not os.environ.get("VERTEXAI_PROJECT"),
        reason="VERTEXAI_PROJECT not set — skipping live test",
    )
    def test_embed_text_returns_normalized_vector(self):
        """embed_text() returns a 3072-dim L2-normalized ndarray via VertexAI ADC."""
        from fastcode.embedder import CodeEmbedder

        config = {
            "embedding": {
                "model": "vertex_ai/gemini-embedding-001",
                "embedding_dim": 3072,
                "batch_size": 32,
                "normalize_embeddings": True,
            }
        }
        embedder = CodeEmbedder(config)
        result = embedder.embed_text("hello world", task_type="RETRIEVAL_QUERY")

        assert isinstance(result, np.ndarray), f"Expected ndarray, got {type(result)}"
        assert result.shape == (3072,), f"Expected shape (3072,), got {result.shape}"
        assert np.all(np.isfinite(result)), "Expected all finite values"
        norm = np.linalg.norm(result)
        assert abs(norm - 1.0) < 1e-5, f"Expected L2 norm ≈ 1.0, got {norm}"
```

### R10: main.py embedding block replacement

```python
# Before (lines 847-851 of fastcode/main.py):
"embedding": {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "device": "cpu",
    "batch_size": 32,
},

# After:
"embedding": {
    "model": "vertex_ai/gemini-embedding-001",
    "embedding_dim": 3072,
    "batch_size": 32,
    "normalize_embeddings": True,
},
```

### R8: requirements.txt edit

```
# Before (line 23):
sentence-transformers

# After:
(line removed entirely)
```

### R9: Dockerfile edit

```dockerfile
# Remove lines 19-21:
# Pre-download the embedding model BEFORE copying app code
# so that code changes don't invalidate this ~470MB cached layer
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

# Also update/remove orphaned comment on line 26:
# Before: "# Copy application code (changes here won't re-download the model)"
# After:  "# Copy application code"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| sentence-transformers local model download at build time | litellm.embedding() API call at request time | Phase 6 (2026-02-25) | Dockerfile no longer bundles a 470MB model layer |
| `"model": "sentence-transformers/all-MiniLM-L6-v2"` in defaults | `"model": "vertex_ai/gemini-embedding-001"` | Phase 7 (this phase) | Config-absent deploys default to VertexAI correctly |
| `device: cpu` in embedding config | No `device` key (server-side model) | Phase 6/7 | Eliminates invalid config key from defaults |

**Deprecated/outdated:**
- `sentence-transformers` package: replaced by `litellm.embedding()` in Phase 6; Phase 7 removes the package reference from requirements.txt and Dockerfile
- Pre-bake Dockerfile RUN layer: was needed to cache the 470MB model; now obsolete since embedding is a remote API call

---

## Open Questions

1. **Should `fastcode/__init__.py` platform import block be included in Phase 7?**
   - What we know: It sets `TOKENIZERS_PARALLELISM`, `OMP_NUM_THREADS`, etc. for sentence-transformers; deferred from Phase 6 per `deferred-items.md`
   - What's unclear: Whether Phase 7 scope should expand to include this cleanup, or whether it requires a separate Phase 8
   - Recommendation: Treat as out-of-scope for Phase 7 unless the user explicitly includes it. The deferred-items.md note is the authoritative record. The phase description does not mention `__init__.py`.

2. **Should `ENV TOKENIZERS_PARALLELISM=false` be removed from Dockerfile?**
   - What we know: R9 requirement only targets the `RUN python -c "..."` pre-bake line; Dockerfile env var is harmless but dead
   - What's unclear: Whether the planner should include this as a bonus R9 cleanup item
   - Recommendation: Include it in R9's task as a "nice to have" cleanup note, but do not make it a requirement gate. The env var is harmless either way.

---

## Validation Architecture

> nyquist_validation not present in .planning/config.json — skipping Validation Architecture section.

*(config.json has no `workflow.nyquist_validation` key; section omitted per instructions.)*

---

## Sources

### Primary (HIGH confidence)

- Direct file inspection: `/Users/knakanishi/Repositories/FastCode/requirements.txt` — confirmed `sentence-transformers` at line 23
- Direct file inspection: `/Users/knakanishi/Repositories/FastCode/Dockerfile` — confirmed pre-bake RUN at line 21
- Direct file inspection: `/Users/knakanishi/Repositories/FastCode/fastcode/main.py` lines 847-851 — confirmed stale embedding defaults
- Direct file inspection: `/Users/knakanishi/Repositories/FastCode/tests/test_vertexai_smoke.py` — confirmed smoke test pattern
- `.planning/REQUIREMENTS.md` — authoritative R8-R11 specification
- `.planning/phases/06-embedder-migration/06-VERIFICATION.md` — confirmed Phase 6 R1-R7 satisfied; R8-R11 explicitly deferred to Phase 7
- `.planning/phases/06-embedder-migration/deferred-items.md` — `__init__.py` platform import is deferred and out of scope

### Secondary (MEDIUM confidence)

- `.planning/phases/06-embedder-migration/06-01-SUMMARY.md` — Phase 6 implementation details confirming new embedder API surface

### Tertiary (LOW confidence)

- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; everything is already in the project
- Architecture: HIGH — direct file inspection of all four target files; exact line numbers confirmed
- Pitfalls: HIGH — order-dependency confirmed by audit note in additional_context; other pitfalls from direct code reading

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (stable — no fast-moving dependencies)
