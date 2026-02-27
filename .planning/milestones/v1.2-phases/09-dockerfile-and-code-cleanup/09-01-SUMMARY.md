---
phase: 09-dockerfile-and-code-cleanup
plan: 01
subsystem: infra
tags: [docker, uv, python, packaging, cache]

# Dependency graph
requires:
  - phase: 08-package-system-foundation
    provides: pyproject.toml with [dependency-groups] dev, uv.lock, hatchling editable install
provides:
  - Dockerfile using uv two-layer cache (deps layer + project layer)
  - Production image excludes dev dependencies (pytest, pytest-asyncio, pytest-cov)
  - .dockerignore verified to allow uv.lock and pyproject.toml in build context
affects:
  - CI/CD image build pipelines
  - Any future Dockerfile modifications

# Tech tracking
tech-stack:
  added: [ghcr.io/astral-sh/uv:0.10.6]
  patterns:
    - uv two-layer Docker cache (bind-mount deps install + project source install)
    - UV_NO_DEV=1 env var to exclude dev dependency-groups from production

key-files:
  created: []
  modified:
    - Dockerfile

key-decisions:
  - "uv pinned to 0.10.6 in COPY --from (per project decision, never :latest)"
  - "Layer 3 uses --mount=type=bind for uv.lock+pyproject.toml so they do not need to be COPY'd"
  - "TOKENIZERS_PARALLELISM removed — was dead since v1.1 sentence-transformers removal (PKG-07)"

patterns-established:
  - "Two-layer uv cache: Layer 3 = uv sync --no-install-project (deps only), Layer 4 = COPY source + uv sync --locked"
  - "UV_NO_DEV=1 set before first uv sync to exclude [dependency-groups] dev from production image"

requirements-completed: [PKG-05, PKG-06, PKG-07]

# Metrics
duration: 2min
completed: 2026-02-26
---

# Phase 9 Plan 01: Dockerfile uv Two-Layer Cache Rewrite Summary

**Dockerfile rewritten from broken pip/requirements.txt install to uv two-layer cache pattern with UV_NO_DEV=1 excluding pytest from production**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-26T09:28:23Z
- **Completed:** 2026-02-26T09:29:42Z
- **Tasks:** 2
- **Files modified:** 1 (Dockerfile; .dockerignore required no changes)

## Accomplishments

- Fixed broken Dockerfile that referenced the deleted requirements.txt (Phase 8 removed it)
- Introduced uv two-layer Docker cache: deps layer cached unless pyproject.toml/uv.lock changes, project layer invalidated on .py changes but does not re-download packages
- Removed dead `TOKENIZERS_PARALLELISM=false` env var (sentence-transformers removed in v1.1)
- Production image now excludes pytest, pytest-asyncio, pytest-cov via UV_NO_DEV=1

## Task Commits

Each task was committed atomically:

1. **Task 1: Verify .dockerignore does not exclude uv.lock or pyproject.toml** - No commit needed (no file changes; .dockerignore already correct)
2. **Task 2: Rewrite Dockerfile with uv two-layer cache pattern** - `d6ca119` (feat)

## Files Created/Modified

- `Dockerfile` - Replaced requirements.txt-based pip install with uv two-layer cache pattern; added uv 0.10.6 binary install; set UV_NO_DEV=1 and UV_LINK_MODE=copy; removed TOKENIZERS_PARALLELISM

## Decisions Made

- uv pinned to `0.10.6` via `COPY --from=ghcr.io/astral-sh/uv:0.10.6` (locked project decision — never use :latest)
- Layer 3 uses `--mount=type=bind` for uv.lock and pyproject.toml so they stay outside the image layer and only invalidate the cache when changed
- `UV_LINK_MODE=copy` required because Docker overlay filesystem does not support hardlinks
- `TOKENIZERS_PARALLELISM` removed per PKG-07 (was dead since sentence-transformers removed in v1.1)
- Task 1 produced no commit because .dockerignore already passes verification (no `*.lock`, `*.toml`, or explicit `uv.lock`/`pyproject.toml` exclusion lines present)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The .dockerignore already excluded neither `uv.lock` nor `pyproject.toml`, so Task 1 required no file modification. Task 2 Dockerfile rewrite passed all 5 automated checks on first attempt.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Dockerfile is ready for `docker build` using the uv two-layer cache pattern
- PKG-05, PKG-06, PKG-07 requirements satisfied
- Remaining Phase 9 plans can proceed (code cleanup tasks)

---
*Phase: 09-dockerfile-and-code-cleanup*
*Completed: 2026-02-26*
