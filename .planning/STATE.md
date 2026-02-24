# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** All LLM calls in FastCode route through litellm, enabling VertexAI on GCP without provider-specific client code.
**Current focus:** Phase 2 — Core Infrastructure

## Current Position

Phase: 2 of 4 (Core Infrastructure)
Plan: 2 of 4 in current phase (02-02 complete)
Status: In progress
Last activity: 2026-02-24 — Plan 02-02 completed

Progress: [█████░░░░░] 50%

## Performance Metrics

**Velocity:**
- Total plans completed: 2
- Average duration: 5min
- Total execution time: 0.2 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-config-and-dependencies | 1 | 6min | 6min |
| 02-core-infrastructure | 2 | 6min | 3min |

**Recent Trend:**
- Last 5 plans: 01-01 (6min), 02-01 (4min), 02-02 (2min)
- Trend: Faster

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Setup]: Replace direct clients (not wrap) — cleaner single path
- [Setup]: Use litellm (not custom abstraction) — battle-tested, already in Nanobot
- [Setup]: ADC for auth (not service account JSON) — standard GCP pattern
- [01-01]: Use vertex_ai/ prefix in litellm model strings (not gemini/) to route through VertexAI with ADC
- [01-01]: Smoke test happy path skips when VERTEXAI_PROJECT unset so CI without GCP credentials stays green
- [01-01]: Broad keyword matching in error test (project/credentials/etc.) avoids fragile assertions on litellm version-specific messages
- [02-01]: count_tokens(model, text) signature reversed from utils.count_tokens(text, model) — consistent with litellm API; callers migrating must update argument order
- [02-01]: Import-time EnvironmentError (not at first call) — fail fast before any LLM call is attempted
- [02-01]: tiktoken cl100k_base fallback for unknown model names in count_tokens
- [02-01]: No logging/exception translation/streaming wrapper — thin pass-through only
- [02-02]: Delete llm_utils.py with callers still present (user-approved) — app intentionally broken until Phase 3/4 migrations complete
- [02-02]: max_tokens fallback logic in llm_utils superseded by litellm.drop_params=True; no stub/shim needed

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 4]: `_stream_with_summary_filter()` chunk boundary behavior with litellm needs empirical testing — litellm chunk sizes may differ from Anthropic's granularity
- [Phase 3]: Gemini system message conversion in `iterative_agent.py` is version-dependent in litellm — verify at implementation time
- [Phase 3/4]: 5 files still import from deleted llm_utils (repo_selector.py, iterative_agent.py, repo_overview.py, answer_generator.py, query_processor.py) — must be migrated before app is functional

## Session Continuity

Last session: 2026-02-24
Stopped at: Completed 02-02-PLAN.md — fastcode/llm_utils.py deleted; 5 callers remain broken pending Phase 3/4 migration
Resume file: None
