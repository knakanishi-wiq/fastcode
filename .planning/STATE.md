# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-26)

**Core value:** All LLM and embedding calls in FastCode route through litellm, enabling full VertexAI on GCP via ADC without provider-specific client code.
**Current focus:** Phase 9 — Dockerfile and Code Cleanup (v1.2)

## Current Position

Phase: 9 of 10 (v1.2 — Dockerfile and Code Cleanup)
Plan: 1 of 3 in current phase
Status: Plan 01 complete
Last activity: 2026-02-26 — Phase 9 Plan 01 complete (Dockerfile rewritten with uv two-layer cache; PKG-05, PKG-06, PKG-07 satisfied)

Progress: [█████████░] 83% (v1.0 + v1.1 complete; v1.2 Phase 8 complete; Phase 9 Plan 01 complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 13 (v1.0: 10 plans, v1.1: 3 plans)
- Average duration: ~2–3 min/plan
- Total execution time: ~0.6 hours

**By Phase:**

| Phase | Plans | Avg/Plan |
|-------|-------|----------|
| 01–05 (v1.0) | 10 | ~2 min |
| 06–07 (v1.1) | 3 | ~2 min |
| 08 (v1.2 Plan 01) | 1 | 2 min |

**Recent Trend:**
- Last 5 plans: 2min, 2min, 3min, 2min, 2min
- Trend: Stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Recent decisions affecting v1.2 (full log in PROJECT.md Key Decisions):

- [v1.2 scope]: PKG-01 requires hatchling editable install — follow PKG-01 spec (editable install for importability), not research recommendation (no build-system)
- [v1.2 scope]: Pin uv to `0.10.6` in Dockerfile; never use `:latest`
- [v1.1 deferred → Phase 10]: MODEL/LITELLM_MODEL independence is operational confusion risk — consolidate in DEBT-04
- [v1.1 deferred → Phase 9]: embed_text() default task_type latent fragility — DEBT-02 makes line 415 explicit
- [08-01]: Used [dependency-groups] dev (PEP 735) rather than [project.optional-dependencies] — stricter isolation, uv recommended approach
- [08-01]: Did NOT add [tool.hatch.build.targets.wheel] — hatchling auto-discovered fastcode/ at repo root without it
- [08-02]: Used git rm to delete requirements.txt atomically; all four Phase 8 success criteria passed on first attempt
- [09-01]: uv pinned to 0.10.6 via COPY --from (never :latest); Task 1 required no .dockerignore changes; TOKENIZERS_PARALLELISM removed as dead env var
- [Phase 09-dockerfile-and-code-cleanup]: Delete all six dead lines from __init__.py (import os, import platform, and Darwin if-block) — leaving either import unused would fail F401 linting
- [Phase 09-dockerfile-and-code-cleanup]: Use uppercase RETRIEVAL_QUERY in retriever.py task_type kwarg — matches embedder.py default exactly to avoid runtime validation error

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 10]: DEBT-03 and DEBT-05 require live GCP credentials (ADC); must run with VERTEXAI_PROJECT set — cannot verify in offline/CI environment

## Session Continuity

Last session: 2026-02-26
Stopped at: Completed 09-01-PLAN.md (Dockerfile rewritten with uv two-layer cache; PKG-05/06/07 satisfied)
Resume file: None
