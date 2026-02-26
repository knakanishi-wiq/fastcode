# Project Research Summary

**Project:** FastCode v1.2 — uv Migration & Tech Debt Cleanup
**Domain:** Python packaging migration (requirements.txt + pip → pyproject.toml + uv.lock + uv Dockerfile)
**Researched:** 2026-02-26
**Confidence:** HIGH

## Executive Summary

FastCode v1.2 is a focused infrastructure migration: replace `requirements.txt` + `pip install` with `pyproject.toml` + `uv.lock` + `uv sync`. This is a well-understood, well-documented migration with official uv tooling that makes it largely mechanical. The entire migration touches exactly five files (create pyproject.toml, create uv.lock, modify Dockerfile, modify .dockerignore, delete requirements.txt), and all application code remains unchanged. The migration delivers two concrete operational improvements: reproducible builds across all environments via the committed lockfile, and Docker rebuild times cut from ~60s to ~5s on source-only changes via uv's layer-caching pattern.

The recommended approach is to use uv as an application manager (not a library manager): no `[build-system]` table, no `hatchling`, no src-layout reorganization. FastCode runs in-place with `python api.py`, and `uv sync --locked` installs dependencies into `.venv` without installing FastCode itself as a package. The uv Docker pattern (bind-mount lockfile in an intermediate layer before COPY source) is the official recommendation from Astral's docs and is the single biggest performance win of the migration.

The key risks are both avoidable with disciplined execution: (1) accidentally gitignoring `uv.lock` defeats reproducibility entirely; (2) leaving pytest/pytest-asyncio/pytest-cov in `[project.dependencies]` instead of `[dependency-groups]` bloats the production Docker image. Both are caught by a simple verification checklist before the PR merges. The migration also carries forward a v1.1 cleanup task: removing the dead `ENV TOKENIZERS_PARALLELISM=false` from the Dockerfile (sentence-transformers was removed in v1.1 but this variable was never cleaned up).

## Key Findings

### Recommended Stack

uv 0.10.6 (latest as of 2026-02-26) is the only new tooling required. All existing validated dependencies (litellm, VertexAI, FastAPI, Docker) are unchanged. The pyproject.toml format follows PEP 517/621; uv.lock is uv's native lockfile format that is cross-platform, diffable, and auto-managed.

FastCode is an application, not a published library. This means no `[build-system]` table is required — `uv sync` installs dependencies without installing FastCode itself as a package. This keeps the pyproject.toml minimal and avoids any src-layout reorganization.

**Core technologies:**
- `uv 0.10.6`: Package manager, lockfile generator, Docker binary source — official Astral tool, 10-100x faster than pip at resolution, native Docker image for `COPY --from` pattern
- `pyproject.toml` (PEP 617/621): Project metadata + runtime dependencies — modern standard; replaces requirements.txt as authoritative dependency declaration
- `uv.lock`: Universal lockfile committed to VCS — provides reproducible installs in Docker and CI; cross-platform (same lockfile for amd64 and arm64); never edited manually

**Critical version requirements:**
- Pin uv to `0.10.6` in Dockerfile (`COPY --from=ghcr.io/astral-sh/uv:0.10.6`); never use `:latest`
- `python:3.12-slim-bookworm` base image unchanged; `requires-python = ">=3.12"` in pyproject.toml
- `litellm[google]>=1.80.8` extras syntax preserved exactly as a quoted TOML string

### Expected Features

All v1.2 features are P1 (must-have for the migration milestone to be complete). There are no table-stakes items that can be deferred without leaving the migration broken or incomplete.

**Must have (table stakes — migration is incomplete without these):**
- `pyproject.toml` with `[project]` table containing all runtime deps from requirements.txt
- `uv.lock` committed to VCS (never gitignored)
- `[dependency-groups] dev` containing pytest, pytest-asyncio, pytest-cov — separated from runtime deps
- Dockerfile updated: uv binary via `COPY --from`, `uv sync --frozen --no-dev` replaces pip, `.venv/bin` on PATH
- Docker layer caching: deps installed before source COPY using `--no-install-project` + bind mounts
- CI updated: `uv sync --locked` replaces `pip install -r requirements.txt`
- `requirements.txt` deleted (not kept alongside pyproject.toml as a "backup")
- `TOKENIZERS_PARALLELISM=false` removed from Dockerfile (dead code from v1.1 sentence-transformers removal)

**Should have (meaningful improvements, add when stable):**
- `uv lock --check` in CI — belt-and-suspenders validation after primary CI is confirmed working
- `UV_COMPILE_BYTECODE=1` in Dockerfile — pre-compiles .pyc at build time for faster container cold-start

**Defer (v2+):**
- `uv run` as primary dev entrypoint — team adoption required; current `python api.py` works fine
- Multi-stage Docker build — only worthwhile if FastCode is restructured as an installable package with entry points

### Architecture Approach

The migration touches exactly five files: create `pyproject.toml`, create `uv.lock`, modify `Dockerfile`, add/modify `.dockerignore`, delete `requirements.txt`. All application code (`fastcode/`, `api.py`, `main.py`, `config/`, `tests/`) is entirely unchanged. The Docker layer flow is deterministic and ordered to maximize cache utilization.

**Major components:**
1. `pyproject.toml` (NEW) — Project metadata + runtime deps in `[project.dependencies]`, test deps in `[dependency-groups]`; no `[build-system]` table; replaces requirements.txt as the authoritative dependency declaration
2. `uv.lock` (NEW) — Committed lockfile; cross-platform; auto-managed by `uv sync`/`uv lock`/`uv add`; never edited manually; the reproducibility guarantee of the entire migration
3. `Dockerfile` (MODIFIED) — Two-phase uv sync with bind mounts for layer caching; uv binary from `ghcr.io/astral-sh/uv:0.10.6`; `ENV PATH="/app/.venv/bin:$PATH"` activates venv for CMD; dead `TOKENIZERS_PARALLELISM=false` removed
4. `.dockerignore` (MODIFIED) — Must exclude `.venv/` to prevent platform-specific local venv from entering Docker build context

**Docker layer order (for maximum cache efficiency):**
```
Layer 1: Base image (python:3.12-slim-bookworm)
Layer 2: apt packages (git, build-essential, curl, ca-certificates)  — rarely invalidated
Layer 3: uv binary COPY --from=ghcr.io/astral-sh/uv:0.10.6           — invalidated only on uv version change
Layer 4: uv sync --frozen --no-dev --no-install-project               — invalidated only on pyproject.toml or uv.lock change
Layer 5: COPY source (fastcode/, api.py, config/)                     — invalidated on any source change
Layer 6: uv sync --frozen --no-dev                                    — fast (deps already in venv from Layer 4)
```

**Dependency resolution flow:**
```
pyproject.toml + uv.lock (generated once)
  → local dev:   uv sync (runtime + dev group, default)
  → local test:  uv sync --group test
  → docker prod: uv sync --frozen --no-dev (runtime only)
  → CI:          uv sync --locked --group test
```

### Critical Pitfalls

1. **uv.lock added to .gitignore** — defeats the entire purpose of migration; CI installs whatever the latest resolution produces rather than what was tested. Prevention: commit uv.lock, add only `.venv/` to .gitignore. Verification: `git ls-files uv.lock` returns the file path.

2. **pytest left in [project.dependencies]** — `uv add -r requirements.txt` puts everything in runtime by default; test frameworks end up in the production Docker image. Prevention: explicitly move pytest/pytest-asyncio/pytest-cov to `[dependency-groups] dev` with `uv add --dev`. Verification: `uv sync --no-dev && python -m pytest` fails with ImportError.

3. **Docker layer cache broken by naive COPY before sync** — every build re-downloads all 30+ packages even on source-only changes; the performance win is lost. Prevention: two-step `--no-install-project` pattern with bind-mounted pyproject.toml + uv.lock. Verification: change only a `.py` file, rebuild Docker, confirm no package downloads in output.

4. **Missing `UV_LINK_MODE=copy` in Dockerfile** — spurious "Failed to hardlink files" warnings fill build logs when `--mount=type=cache` is used (Docker cache mounts create a separate filesystem that blocks hard links). Prevention: `ENV UV_LINK_MODE=copy` after copying the uv binary. Recovery cost: LOW.

5. **Keeping requirements.txt alongside pyproject.toml** — two sources of truth diverge silently; developers or CI may continue using the stale file; Dockerfile may still pip-install from the old file if not updated. Prevention: delete requirements.txt in the same commit that creates pyproject.toml + uv.lock.

## Implications for Roadmap

All work fits in two phases that mirror the natural dependency order: first establish the lockfile system (nothing else works without pyproject.toml + uv.lock), then update the execution environments (Dockerfile + CI). The phases are independent enough to be a single PR, but separating them makes review cleaner.

### Phase 1: Package System Migration

**Rationale:** Everything downstream (Docker, CI, developer workflow) requires pyproject.toml + uv.lock to exist first. This phase is purely file creation with zero risk to runtime behavior — no application code changes.

**Delivers:** `pyproject.toml` with all runtime deps, `uv.lock` committed to VCS, `[dependency-groups] dev` with test packages properly separated, `requirements.txt` deleted. Developer `uv sync` works locally.

**Addresses:** All P1 table-stakes features except Dockerfile and CI updates.

**Avoids:**
- Pitfall 1 (uv.lock gitignored): verified by `git ls-files uv.lock` before proceeding to Phase 2
- Pitfall 2 (pytest in runtime): verified by `uv sync --no-dev && python -m pytest` failing with ImportError
- Pitfall 5 (keeping requirements.txt): deleted in same commit as pyproject.toml creation

**Key actions:**
1. `uv init --no-workspace` to scaffold pyproject.toml skeleton
2. `uv add -r requirements.txt` to bulk-migrate all runtime deps into `[project.dependencies]`
3. `uv remove pytest pytest-asyncio pytest-cov && uv add --dev pytest pytest-asyncio pytest-cov` to move test deps to `[dependency-groups]`
4. Verify `litellm[google]>=1.80.8` and `mcp[cli]` extras are preserved as correctly quoted TOML strings
5. Commit `pyproject.toml` + `uv.lock`; `git rm requirements.txt`

### Phase 2: Dockerfile and CI Migration

**Rationale:** The Dockerfile and CI both depend on `uv.lock` existing in VCS — Phase 1 must be complete and merged first. This phase replaces the execution environment without changing any application behavior.

**Delivers:** Docker builds using two-phase `uv sync --frozen --no-dev` with layer caching (deps cached separately from source); CI using `uv sync --locked`; `TOKENIZERS_PARALLELISM=false` removed; `.dockerignore` updated to exclude `.venv/`.

**Implements:** Architecture Pattern 2 (intermediate layer caching with `--no-install-project` bind mounts) from ARCHITECTURE.md.

**Avoids:**
- Pitfall 3 (layer cache broken): `--no-install-project` two-step ensures deps layer caches until uv.lock changes, not until source changes
- Pitfall 4 (UV_LINK_MODE missing): `ENV UV_LINK_MODE=copy` added alongside the uv binary COPY
- Technical debt: dead `TOKENIZERS_PARALLELISM=false` ENV removed

**Key actions:**
1. Replace `COPY requirements.txt` + `pip install` block with uv binary COPY + two-phase `uv sync --frozen --no-dev`
2. Add `ENV PATH="/app/.venv/bin:$PATH"` to activate venv for CMD
3. Add `ENV UV_LINK_MODE=copy`; optionally add `ENV UV_COMPILE_BYTECODE=1` for P2 bytecode optimization
4. Remove `ENV TOKENIZERS_PARALLELISM=false`
5. Update `.dockerignore` to exclude `.venv/`
6. Update CI workflow: replace `pip install -r requirements.txt` with `uv sync --locked`
7. Verify: change only a `.py` file, rebuild Docker, confirm no package downloads in Layer 4

### Phase Ordering Rationale

- Phase 1 must precede Phase 2: `uv sync --locked` and `uv sync --frozen` both require `uv.lock` to exist in the build context
- Both phases can be a single PR or two sequential PRs — neither changes application behavior, so the risk is the same either way; a single PR is simpler to review
- Verification of Phase 1 (local `uv sync` works, pytest correctly excluded from `--no-dev` install) should be confirmed before Phase 2 begins, to catch any resolution failures from lockfile generation before they manifest in Docker/CI

### Research Flags

Phases with standard patterns (no deeper research needed — skip `/gsd:research-phase`):
- **Phase 1 (pyproject.toml + uv.lock):** Extensively documented in official uv docs with first-class migration path; all pitfalls have known prevention steps and low recovery cost
- **Phase 2 (Dockerfile + CI):** The two-phase `--no-install-project` pattern is the official uv Docker recommendation with published examples; no ambiguity about target state

No phases need deeper research during planning. This is a single-tool migration with complete official documentation, verified local tooling (uv 0.10.4 installed), and a known working reference (the nanobot pyproject.toml in this same repo demonstrates the format, albeit for a library rather than an app).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | uv 0.10.6 verified from official GitHub releases page; all patterns sourced from official docs.astral.sh; uv 0.10.4 confirmed installed locally |
| Features | HIGH | uv CLI behavior verified locally (`uv help sync`, `uv help add`); `--frozen` vs `--locked` vs default semantics confirmed from official sync docs; `[dependency-groups]` PEP 735 behavior verified |
| Architecture | HIGH | Docker patterns sourced from official uv Docker integration guide with full examples; anti-patterns explicitly documented by Astral |
| Pitfalls | HIGH (core) / MEDIUM (native packages) | Critical pitfalls (gitignore, dep groups, layer cache, link mode) are HIGH from official docs and direct codebase analysis; faiss-cpu and tree-sitter wheel availability are MEDIUM — confirmed for amd64, ARM Linux is a known gap |

**Overall confidence:** HIGH

### Gaps to Address

- **faiss-cpu on non-amd64 platforms:** Wheels confirmed for `linux/amd64`, `macos/arm64`, `macos/x86_64`. If FastCode ever needs `linux/arm64` (e.g., AWS Graviton), faiss-cpu may need source compilation. Not a current concern given the `python:3.12-slim-bookworm` amd64 Dockerfile — no action needed for v1.2.
- **uv.lock merge conflicts from parallel branches:** When two branches both run `uv add`, `uv.lock` will have conflicts on merge. Resolution is always "run `uv lock` on the merged branch" — uv regenerates a clean lockfile. Worth documenting in contributor guidelines post-migration, not a blocker.
- **nanobot workspace isolation confirmed:** nanobot has its own `pyproject.toml` + hatchling setup in this repo. Research explicitly validates keeping FastCode's pyproject.toml independent (no `[tool.uv.workspace]`). The two packages have independent dep graphs and Python version constraints — this is the correct configuration.

## Sources

### Primary (HIGH confidence)
- uv 0.10.6 releases: https://github.com/astral-sh/uv/releases/latest — version confirmed
- uv Docker integration guide: https://docs.astral.sh/uv/guides/integration/docker/ — layer caching pattern, `--no-install-project`, env vars
- uv project dependencies: https://docs.astral.sh/uv/concepts/projects/dependencies/ — `[dependency-groups]` vs `[project.optional-dependencies]`
- uv sync concepts: https://docs.astral.sh/uv/concepts/projects/sync/ — `--frozen` vs `--locked` vs default semantics
- uv project guide: https://docs.astral.sh/uv/guides/projects/ — `uv add -r requirements.txt` migration path
- uv project init: https://docs.astral.sh/uv/concepts/projects/init/ — application mode (no build backend)
- uv settings reference: https://docs.astral.sh/uv/reference/settings/ — UV_LINK_MODE, UV_COMPILE_BYTECODE, UV_NO_DEV
- uv 0.10.4 CLI (local): `uv help sync`, `uv help add`, `uv help lock` — behavior verified directly

### Secondary (codebase analysis)
- `/Users/knakanishi/Repositories/FastCode/requirements.txt` — source of truth for 35 current deps; pytest family identified as test-only
- `/Users/knakanishi/Repositories/FastCode/Dockerfile` — current pattern to be replaced; `TOKENIZERS_PARALLELISM=false` confirmed as dead code from v1.1
- `/Users/knakanishi/Repositories/FastCode/nanobot/pyproject.toml` — reference for hatchling + `[project.optional-dependencies]` pattern; contrasted against FastCode's needs as an app (not a library)

---
*Research completed: 2026-02-26*
*Ready for roadmap: yes*
