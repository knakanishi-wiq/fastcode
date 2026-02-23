# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** All LLM calls in FastCode route through litellm, enabling VertexAI on GCP without provider-specific client code.
**Current focus:** Phase 1 — Config and Dependencies

## Current Position

Phase: 1 of 4 (Config and Dependencies)
Plan: 1 of 1 in current phase (01-01 complete)
Status: In progress
Last activity: 2026-02-24 — Plan 01-01 completed

Progress: [██░░░░░░░░] 20%

## Performance Metrics

**Velocity:**
- Total plans completed: 1
- Average duration: 6min
- Total execution time: 0.1 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-config-and-dependencies | 1 | 6min | 6min |

**Recent Trend:**
- Last 5 plans: 01-01 (6min)
- Trend: -

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

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 4]: `_stream_with_summary_filter()` chunk boundary behavior with litellm needs empirical testing — litellm chunk sizes may differ from Anthropic's granularity
- [Phase 3]: Gemini system message conversion in `iterative_agent.py` is version-dependent in litellm — verify at implementation time

## Session Continuity

Last session: 2026-02-24
Stopped at: Completed 01-01-PLAN.md — litellm installed, .env.example configured, smoke tests passing
Resume file: None
