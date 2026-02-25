---
phase: 03-non-streaming-migration
plan: 04
subsystem: llm
tags: [litellm, openai, anthropic, iterative-agent, migration, requirements]

# Dependency graph
requires:
  - phase: 03-non-streaming-migration/03-02
    provides: repo_selector.py migrated to llm_client
  - phase: 03-non-streaming-migration/03-03
    provides: repo_overview.py migrated to llm_client
  - phase: 02-core-infrastructure/02-01
    provides: llm_client module with completion() and DEFAULT_MODEL
provides:
  - "iterative_agent.py routes all LLM calls through llm_client.completion() with system message in messages list"
  - "All four Phase 3 target files (query_processor, repo_selector, repo_overview, iterative_agent) are clean of direct openai/anthropic client code"
  - "openai/anthropic remain in requirements.txt — answer_generator.py still imports them (deferred to Phase 4)"
affects: [04-streaming-migration, answer_generator.py migration]

# Tech tracking
tech-stack:
  added: []
  patterns: [system-message-in-messages-list, llm_client-completion-single-path]

key-files:
  created: []
  modified:
    - fastcode/iterative_agent.py

key-decisions:
  - "os import kept in iterative_agent.py — used for path operations (os.path.join, os.path.exists, os.listdir, os.path.isdir) throughout ~3200-line file"
  - "System message passed in messages list (not as system= kwarg) — litellm converts to Gemini systemInstruction field automatically with vertex_ai/ prefix"
  - "openai and anthropic kept in requirements.txt — answer_generator.py still imports them directly; deferred to Phase 4 per Pitfall 5 in RESEARCH.md"
  - "Dead constructor state (provider, model, api_key, anthropic_api_key, base_url, client, _initialize_client) removed entirely"

patterns-established:
  - "Pattern: System message in messages list (not system= kwarg) for litellm/Gemini/VertexAI compatibility"

requirements-completed: [MIGR-02, MIGR-05]

# Metrics
duration: 2min
completed: 2026-02-24
---

# Phase 3 Plan 04: iterative_agent.py Migration to llm_client Summary

**iterative_agent.py (~3200 lines) migrated off direct openai/anthropic clients to llm_client.completion() with system message in messages list; all four Phase 3 target files now clean**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T06:34:13Z
- **Completed:** 2026-02-24T06:36:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Removed all direct openai/anthropic/llm_utils imports and provider dispatch from iterative_agent.py
- Removed dead constructor state: provider, model, api_key, anthropic_api_key, base_url, client, _initialize_client
- Replaced provider-dispatching _call_llm() with single llm_client.completion() call, system message in messages list
- All four Phase 3 migration targets (query_processor.py, repo_selector.py, repo_overview.py, iterative_agent.py) now clean
- Test suite passes: 10/10 tests in tests/test_llm_client.py
- openai/anthropic kept in requirements.txt — answer_generator.py still imports them directly (deferred to Phase 4)

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate iterative_agent.py to llm_client** - `03baaab` (refactor)
2. **Task 2: Check requirements.txt and run final test suite** - No commit needed (requirements.txt unchanged; answer_generator.py still needs openai/anthropic)

**Plan metadata:** (final docs commit)

## Files Created/Modified
- `fastcode/iterative_agent.py` - Removed openai/anthropic/llm_utils imports, dead constructor state, _initialize_client method, and provider dispatch in _call_llm(); now uses llm_client.completion() with system message in messages list

## Decisions Made
- **os import kept** — iterative_agent.py uses os extensively for path operations (os.path.join, os.path.exists, os.listdir, os.path.isdir, os.path.basename, etc.) throughout the ~3200-line file
- **System message in messages list** — system= kwarg may be silently dropped by litellm; passing it in the messages list ensures litellm converts it to Gemini's systemInstruction field automatically when using the vertex_ai/ prefix
- **requirements.txt unchanged** — answer_generator.py still has `from openai import OpenAI`, `from anthropic import Anthropic`, and `from .llm_utils import openai_chat_completion`; removing openai/anthropic now would break it; deferred to Phase 4

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## Next Phase Readiness
- Phase 3 (non-streaming migration) is complete: all four target files migrated
- Phase 4 (streaming migration) can proceed — answer_generator.py is the last file with direct openai/anthropic client code and llm_utils dependency
- Blocker note: answer_generator.py still imports from deleted llm_utils (along with openai/anthropic) — Phase 4 must handle this before the app is fully functional

---
*Phase: 03-non-streaming-migration*
*Completed: 2026-02-24*

## Self-Check: PASSED

- FOUND: fastcode/iterative_agent.py
- FOUND: .planning/phases/03-non-streaming-migration/03-04-SUMMARY.md
- FOUND: commit 03baaab (refactor(03-04): migrate iterative_agent.py to llm_client)
