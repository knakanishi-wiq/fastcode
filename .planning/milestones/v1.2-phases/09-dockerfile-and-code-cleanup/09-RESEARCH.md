# Phase 9: Dockerfile and Code Cleanup - Research

**Researched:** 2026-02-26
**Domain:** Docker layer caching with uv, Python dead code removal
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PKG-05 | `Dockerfile` installs dependencies via `uv sync --frozen` with two-layer caching: layer 1 installs deps without project (`--no-install-project`), layer 2 installs the project itself | uv Docker guide pattern verified via official docs |
| PKG-06 | Docker builds exclude dev deps (`UV_NO_DEV=1`); production image has no pytest or test infrastructure | `ENV UV_NO_DEV=1` + `uv sync --locked` pattern verified via official docs |
| PKG-07 | `ENV TOKENIZERS_PARALLELISM=false` removed from `Dockerfile` (dead env var after sentence-transformers removal in v1.1) | Current Dockerfile inspected at line 33; env var is present and must be deleted |
| DEBT-01 | Dead platform import block removed from `fastcode/__init__.py` (OS-specific tokenizer env vars became no-ops after sentence-transformers removal) | Current `__init__.py` lines 6-13 inspected; block sets `TOKENIZERS_PARALLELISM`, `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS` — all dead |
| DEBT-02 | `retriever.py` line 415 passes `task_type="RETRIEVAL_QUERY"` explicitly instead of relying on `embed_text()` default | `embed_text()` confirmed at `fastcode/embedder.py:28` with default `task_type="RETRIEVAL_QUERY"`; line 415 calls `self.embedder.embed_text(semantic_query_text)` with no task_type arg |
</phase_requirements>

## Summary

Phase 9 is a pure mechanical change phase: rewrite the `Dockerfile` to use uv with layer caching, and remove two small dead-code items from Python source files. There is no new logic to introduce. All three work streams (Dockerfile rewrite, `__init__.py` cleanup, `retriever.py` explicit arg) are independent and can be planned as separate tasks.

The Dockerfile rewrite is the most involved change. The current Dockerfile uses the legacy `pip install -r requirements.txt` pattern with `requirements.txt` (which Phase 8 deleted from VCS). That file reference is now broken — the Dockerfile must be completely rewritten. The new pattern follows the official uv Docker guide: copy uv binary from `ghcr.io/astral-sh/uv:0.10.6`, mount `pyproject.toml` and `uv.lock` for the dependency layer, then copy source and sync the project. A locked decision from STATE.md pins uv to `0.10.6` in the Dockerfile.

The two code cleanups are single-line-range deletions: remove lines 6-13 from `fastcode/__init__.py` (the `platform`/`os` import block), and add `task_type="RETRIEVAL_QUERY"` as an explicit keyword argument on `fastcode/retriever.py:415`.

**Primary recommendation:** Rewrite the Dockerfile wholesale using the uv two-layer cache pattern; delete dead platform block from `__init__.py`; add explicit `task_type=` kwarg at retriever.py:415.

## Standard Stack

### Core

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| uv | 0.10.6 (pinned) | Package installer / sync in Docker | PROJECT DECISION — locked in STATE.md |
| ghcr.io/astral-sh/uv | image tag `0.10.6` | Copy uv binary into Docker image | Official uv distribution mechanism |
| python:3.12-slim-bookworm | current | Base image | Already in use in project |

### Supporting

| Mechanism | Purpose | When to Use |
|-----------|---------|-------------|
| `--mount=type=cache,target=/root/.cache/uv` | Persist uv's package cache across builds | Every `uv sync` RUN instruction |
| `ENV UV_NO_DEV=1` | Exclude dependency-groups.dev from sync | Set before any `uv sync` call |
| `ENV UV_LINK_MODE=copy` | Prevent "hardlink failed" warnings in Docker | Required because Docker overlayfs doesn't support hardlinks |
| `uv sync --locked --no-install-project` | Install only deps (not the project package) | Layer 1 — changes infrequently |
| `uv sync --locked` | Install project package itself into venv | Layer 2 — changes with every source edit |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `uv sync --locked` | `uv sync --frozen` | `--frozen` is stricter (errors if lock is out of date at runtime); `--locked` is the current canonical flag for Docker; use `--locked` |
| Two-stage (deps + project layers) | Single `uv sync --locked` | Single layer is simpler but invalidates cache on every `.py` change; two-layer is required by PKG-05 |
| `COPY uv.lock pyproject.toml ./` | `--mount=type=bind` | bind mounts are ephemeral and don't persist in image layers — correct for deps phase; COPY is needed before project source COPY |

## Architecture Patterns

### Recommended Dockerfile Structure

```
Layer 1 (system deps):   apt-get install git build-essential curl
Layer 2 (uv binary):     COPY --from=ghcr.io/astral-sh/uv:0.10.6
Layer 3 (Python deps):   uv sync --locked --no-install-project  [cached on pyproject.toml/uv.lock changes only]
Layer 4 (project):       COPY source + uv sync --locked         [cached on .py file changes]
Layer 5 (dirs/config):   mkdir + EXPOSE + ENV + CMD
```

### Pattern 1: uv Two-Layer Cache Dockerfile

**What:** Separate dependency installation (layer 3) from project source installation (layer 4) so that editing a `.py` file only invalidates layer 4.

**When to use:** Any Docker build where dependencies are stable but source changes frequently — which describes FastCode exactly.

**Example:**
```dockerfile
# Source: https://docs.astral.sh/uv/guides/integration/docker/

FROM python:3.12-slim-bookworm

# --- System dependencies ---
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git build-essential curl ca-certificates && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# --- Install uv (pinned version per project decision) ---
COPY --from=ghcr.io/astral-sh/uv:0.10.6 /uv /uvx /bin/

WORKDIR /app

# --- Layer 3: Dependencies (cached unless pyproject.toml or uv.lock changes) ---
ENV UV_NO_DEV=1
ENV UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# --- Layer 4: Project source (invalidated on any .py change) ---
COPY fastcode/ fastcode/
COPY api.py ./
COPY config/ config/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# --- Runtime setup ---
RUN mkdir -p /app/repos /app/data /app/logs
EXPOSE 8001
ENV PYTHONUNBUFFERED=1
CMD ["python", "api.py", "--host", "0.0.0.0", "--port", "8001"]
```

### Pattern 2: Run via uv venv

When `uv sync` is used, the project is installed into `.venv` inside `/app`. The CMD should invoke the venv Python, or rely on uv's path management. The simplest approach consistent with current project CMD is to use `.venv/bin/python` or add `.venv/bin` to PATH:

```dockerfile
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "api.py", "--host", "0.0.0.0", "--port", "8001"]
```

This is the standard pattern from official uv Docker docs.

### Anti-Patterns to Avoid

- **Copying `requirements.txt`:** `requirements.txt` was deleted in Phase 8. The Dockerfile currently references it at line 16 — this is broken and must be replaced entirely.
- **`COPY . /app` as first step:** This invalidates the dependency layer on every source change. Always bind-mount only `pyproject.toml` + `uv.lock` for the deps layer.
- **`ENV TOKENIZERS_PARALLELISM=false` in Dockerfile:** Dead since sentence-transformers was removed in v1.1. PKG-07 requires deleting this line.
- **`uv sync` without `--locked`:** Never omit `--locked` in Docker; it guarantees reproducibility from the committed `uv.lock`.
- **Dev deps in production image:** `ENV UV_NO_DEV=1` must be set before any `uv sync` call. Without it, pytest and test infrastructure are installed in production.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Package cache persistence | Custom download cache logic | `--mount=type=cache,target=/root/.cache/uv` | BuildKit native; handles concurrency, eviction automatically |
| Dev dep exclusion | Custom pyproject.toml manipulation | `ENV UV_NO_DEV=1` | uv reads `[dependency-groups]` automatically when this env var is set |
| uv install in image | `curl` + manual install script | `COPY --from=ghcr.io/astral-sh/uv:0.10.6` | Official distribution pattern; pinned, reproducible |

**Key insight:** All Docker/uv complexity is solved by uv's official patterns. No custom scripts needed.

## Common Pitfalls

### Pitfall 1: Broken requirements.txt Reference

**What goes wrong:** The current `Dockerfile` line 16-17 references `requirements.txt` with `COPY requirements.txt ./` and `pip install -r requirements.txt`. Phase 8 deleted `requirements.txt`. The Dockerfile is currently broken.
**Why it happens:** Phase 8 only deleted the file and updated `pyproject.toml`/`uv.lock`; Dockerfile update was deferred to Phase 9.
**How to avoid:** The entire `COPY requirements.txt` + `pip install` block must be replaced with the uv two-layer pattern. This is a complete rewrite of the install section, not a patch.
**Warning signs:** `docker build` fails with `COPY failed: file not found in build context`.

### Pitfall 2: Missing ENV PATH for venv

**What goes wrong:** After `uv sync`, the project is in `/app/.venv`. The CMD `python api.py` resolves to `/usr/bin/python` (the system Python), not the venv Python.
**Why it happens:** `uv sync` creates `.venv` but doesn't activate it for subsequent CMD calls.
**How to avoid:** Add `ENV PATH="/app/.venv/bin:$PATH"` to the Dockerfile so `python` resolves to the venv interpreter.
**Warning signs:** `ModuleNotFoundError` at container startup despite successful `uv sync`.

### Pitfall 3: UV_LINK_MODE Not Set

**What goes wrong:** Build produces warnings: `warning: Failed to hardlink files; falling back to full copy`.
**Why it happens:** Docker's overlay filesystem doesn't support hardlinks between layers; uv tries hardlinks by default.
**How to avoid:** Set `ENV UV_LINK_MODE=copy` before any `uv sync` step.
**Warning signs:** Build warnings mentioning hardlink failures (non-fatal but noisy).

### Pitfall 4: uv.lock Not Present in Build Context

**What goes wrong:** The bind mount `--mount=type=bind,source=uv.lock` fails if `uv.lock` is in `.dockerignore`.
**Why it happens:** Overly aggressive `.dockerignore` rules.
**How to avoid:** Verify `uv.lock` is NOT excluded by `.dockerignore`. Phase 8 committed `uv.lock` to VCS; it must also be present in the build context.
**Warning signs:** `failed to solve: failed to read file content: file does not exist`.

### Pitfall 5: Dead Import Block Leaves Unused imports

**What goes wrong:** After removing lines 6-13 from `__init__.py`, the `import os` and `import platform` lines become unused. Both must be deleted as part of DEBT-01 cleanup.
**Why it happens:** The entire block (`import os`, `import platform`, and the `if platform.system() == 'Darwin':` block) is dead code together.
**How to avoid:** Delete all six lines (6 through 13 inclusive) in one edit, not just the if-block.
**Warning signs:** Linters report `F401 'os' imported but unused` and `F401 'platform' imported but unused`.

### Pitfall 6: Wrong task_type String for DEBT-02

**What goes wrong:** Using `task_type="retrieval_query"` (lowercase) instead of `task_type="RETRIEVAL_QUERY"` (uppercase).
**Why it happens:** Typo or confusion with litellm's casing conventions.
**How to avoid:** Use `task_type="RETRIEVAL_QUERY"` — this is the existing default in `embedder.py:28`; the keyword argument must match exactly.
**Warning signs:** Embedding call fails at runtime with task_type validation error.

## Code Examples

Verified patterns from official sources:

### Complete Target Dockerfile

```dockerfile
# Source: https://docs.astral.sh/uv/guides/integration/docker/
# uv version pinned to 0.10.6 per project decision (STATE.md)

FROM python:3.12-slim-bookworm

# System dependencies for tree-sitter and git
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        build-essential \
        curl \
        ca-certificates && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Install uv (pinned)
COPY --from=ghcr.io/astral-sh/uv:0.10.6 /uv /uvx /bin/

WORKDIR /app

# Layer 3: Install dependencies only (cached unless pyproject.toml/uv.lock change)
ENV UV_NO_DEV=1
ENV UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Layer 4: Install project (invalidated on source changes)
COPY fastcode/ fastcode/
COPY api.py ./
COPY config/ config/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Runtime directories
RUN mkdir -p /app/repos /app/data /app/logs

EXPOSE 8001

ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "api.py", "--host", "0.0.0.0", "--port", "8001"]
```

### Target fastcode/__init__.py (after DEBT-01)

```python
# Source: fastcode/__init__.py — lines 1-5 and 15+ are kept; lines 6-13 are deleted

"""
FastCode 2.0 - Repository-Level Code Understanding System
With Multi-Repository Support
"""

from .main import FastCode
from .loader import RepositoryLoader
# ... rest of imports unchanged
```

Lines to delete (6-13 inclusive):
```python
import os
import platform

if platform.system() == 'Darwin':
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['OMP_NUM_THREADS'] = '1'
    os.environ['OPENBLAS_NUM_THREADS'] = '1'
    os.environ['MKL_NUM_THREADS'] = '1'
```

### Target retriever.py line 415 (after DEBT-02)

```python
# Before (line 415):
query_embedding = self.embedder.embed_text(semantic_query_text)

# After (DEBT-02 fix):
query_embedding = self.embedder.embed_text(semantic_query_text, task_type="RETRIEVAL_QUERY")
```

The `embed_text` signature at `fastcode/embedder.py:28`:
```python
def embed_text(self, text: str, task_type: str = "RETRIEVAL_QUERY") -> np.ndarray:
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pip install -r requirements.txt` in Docker | `uv sync --locked` with layer caching | Phase 9 (this phase) | Faster rebuilds, reproducible, no dev deps in production |
| `requirements.txt` as dependency source | `pyproject.toml` + `uv.lock` | Phase 8 (complete) | Single source of truth; `requirements.txt` deleted |
| `ENV TOKENIZERS_PARALLELISM=false` in Dockerfile | Deleted | Phase 9 (this phase) | sentence-transformers removed in v1.1; env var was no-op |
| OS-detection block in `__init__.py` | Deleted | Phase 9 (this phase) | Dead code since v1.1 embedding migration |

**Deprecated/outdated in this codebase:**
- `COPY requirements.txt ./` + `pip install -r requirements.txt`: Broken (file deleted). Replace with uv pattern.
- `import os` / `import platform` in `__init__.py`: Only used by the dead platform block. Delete both.
- `ENV TOKENIZERS_PARALLELISM=false` in `Dockerfile`: Dead env var. Delete line 33 of current Dockerfile.

## Open Questions

1. **Does `config/` directory exist and should it be COPYed?**
   - What we know: Current Dockerfile includes `COPY config/ config/`. The directory exists in the project.
   - What's unclear: Whether `config/` is used at runtime by `api.py`.
   - Recommendation: Preserve `COPY config/ config/` in the rewritten Dockerfile unless the planner confirms it is unused.

2. **Should `--no-editable` be used?**
   - What we know: uv docs recommend `--no-editable` in multi-stage builds to decouple from source. Single-stage builds (like current) don't require it.
   - What's unclear: Whether the project intends a single-stage or multi-stage Docker build.
   - Recommendation: Use single-stage (matching current pattern) without `--no-editable`. PKG-05 does not mention multi-stage.

3. **Does `.dockerignore` need updating?**
   - What we know: A `.dockerignore` file may or may not exist; `uv.lock` must be in the build context.
   - What's unclear: Current `.dockerignore` contents.
   - Recommendation: Planner should include a task to verify `.dockerignore` does not exclude `uv.lock` or `pyproject.toml`.

## Sources

### Primary (HIGH confidence)
- https://docs.astral.sh/uv/guides/integration/docker/ — Verified via WebFetch: two-layer pattern, UV_NO_DEV, UV_LINK_MODE, bind-mount strategy, version pinning
- `/Users/knakanishi/Repositories/FastCode/Dockerfile` — Current Dockerfile inspected directly
- `/Users/knakanishi/Repositories/FastCode/fastcode/__init__.py` — Dead platform block confirmed at lines 6-13
- `/Users/knakanishi/Repositories/FastCode/fastcode/retriever.py` — Line 415 `embed_text` call confirmed without task_type
- `/Users/knakanishi/Repositories/FastCode/fastcode/embedder.py:28` — `embed_text` default `task_type="RETRIEVAL_QUERY"` confirmed
- `/Users/knakanishi/Repositories/FastCode/.planning/STATE.md` — Locked decision: pin uv to `0.10.6`

### Secondary (MEDIUM confidence)
- None required — all critical facts verified from primary sources

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — uv Docker pattern verified directly from official docs; project files inspected
- Architecture: HIGH — Dockerfile rewrite pattern is exact from official uv integration guide
- Pitfalls: HIGH — broken `requirements.txt` reference confirmed by direct file inspection; other pitfalls from official docs

**Research date:** 2026-02-26
**Valid until:** 2026-03-28 (uv Docker API is stable; 30-day window appropriate)
