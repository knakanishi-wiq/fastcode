# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** All LLM calls in FastCode route through litellm, enabling VertexAI on GCP without provider-specific client code.
**Current focus:** Phase 4 — Streaming Migration and Finalization

## Current Position

Phase: 4 of 4 (Streaming Migration and Finalization)
Plan: 2 of 4 in current phase (04-02 complete)
Status: In progress
Last activity: 2026-02-25 — Plan 04-02 completed

Progress: [█████████░] 90%

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
| 03-non-streaming-migration | 4 | 8min | 2min |

**Recent Trend:**
- Last 5 plans: 02-02 (2min), 03-01 (2min), 03-02 (2min), 03-03 (2min), 03-04 (2min)
- Trend: Faster

*Updated after each plan completion*
| Phase 03-non-streaming-migration P04 | 2min | 2 tasks | 1 files |
| Phase 04-streaming-migration P02 | 2min | 2 tasks | 2 files |

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
- [03-01]: Remove os import entirely since all usages were in the dead constructor code being removed
- [03-01]: Replace provider dispatch + _call_openai/_call_anthropic with single _call_llm() method calling llm_client.completion()
- [03-01]: _should_use_llm_enhancement guard simplified — no instance-level client to check, use_llm_enhancement flag is sufficient
- [03-02]: Both dispatch blocks in RepositorySelector replaced (select_relevant_files AND select_relevant_repos had identical provider branches)
- [03-02]: if not self.llm_client guards removed from both methods — llm_client module always available, errors bubble up as exceptions
- [03-02]: os import removed entirely — all usages were in dead constructor code
- [03-03]: os import kept in repo_overview.py — used for path operations (os.path.join, os.path.exists, os.sep, os.path.dirname, os.path.basename)
- [03-03]: generate_overview guard simplified from 'if readme_content and self.llm_client' to 'if readme_content' — llm_client module always available
- [03-03]: Unreachable fallback return after try/except removed — only triggered when provider was neither openai nor anthropic
- [Phase 03-04]: os import kept in iterative_agent.py — used for path operations throughout ~3200-line file
- [Phase 03-04]: System message in messages list (not system= kwarg) for litellm/Gemini/VertexAI compatibility
- [Phase 03-04]: openai/anthropic kept in requirements.txt — answer_generator.py still imports them; deferred to Phase 4
- [04-02]: No replacement for deleted provider field — litellm routing controlled entirely by MODEL env var prefix (vertex_ai/...)
- [04-02]: All BASE_URL references removed from .env.example — litellm vertex_ai/ prefix + ADC handles endpoint routing without manual base URL

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 4]: `_stream_with_summary_filter()` chunk boundary behavior with litellm needs empirical testing — litellm chunk sizes may differ from Anthropic's granularity
- [Phase 3/4]: 1 file still imports from deleted llm_utils (answer_generator.py) — must be migrated before app is functional; all 4 Phase 3 files now fixed

## Session Continuity

Last session: 2026-02-25
Stopped at: Completed 04-02-PLAN.md — config.yaml and .env.example cleaned of provider-specific fields; config now accurately reflects litellm/VertexAI-only architecture
Resume file: None
