# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** All LLM calls in FastCode route through litellm, enabling VertexAI on GCP without provider-specific client code.
**Current focus:** Milestone v1.1 — VertexAI Embedding Migration

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-02-25 — Milestone v1.1 started

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
| Phase 04-streaming-migration P01 | 3min | 2 tasks | 1 files |
| Phase 05-fix-answer-generator-wiring-and-cleanup P01 | 3min | 2 tasks | 3 files |

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
- [04-01]: os import kept in answer_generator.py — still needed for os.getenv('MODEL') in __init__
- [04-01]: raw_response variable name preserved in generate() — used downstream by _parse_response_with_summary() in multi-turn mode
- [04-01]: None-guard (or '' + if not chunk_text: continue) applied to both streaming loops per RESEARCH.md litellm pitfall
- [04-01]: _stream_with_summary_filter() chunk variable is plain string (same type as before) — buffering/regex logic unchanged
- [05-01]: count_tokens removed from utils import in answer_generator.py — fully routed through llm_client module
- [05-01]: MODEL fallback uses llm_client.DEFAULT_MODEL (not hardcoded string) — single source of truth for default model
- [05-01]: openai and anthropic removed from requirements.txt — no fastcode/ file imports them post-Phase 4
- [05-01]: .env.example MODEL updated from placeholder to vertex_ai/ prefix example; LITELLM_MODEL entry added

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 4]: `_stream_with_summary_filter()` chunk boundary behavior with litellm needs empirical testing — litellm chunk sizes may differ from Anthropic's granularity
- [RESOLVED]: answer_generator.py was last file importing from deleted llm_utils — now migrated; runtime ImportError eliminated

## Session Continuity

Last session: 2026-02-25
Stopped at: Completed 05-01-PLAN.md — answer_generator.py fully wired to llm_client token counting; 6 count_tokens call sites fixed; MODEL=None risk eliminated; dead openai/anthropic deps removed; Phase 5 complete
Resume file: None
