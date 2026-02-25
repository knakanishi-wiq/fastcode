---
phase: 05-fix-answer-generator-wiring-and-cleanup
plan: 01
subsystem: llm
tags: [litellm, answer_generator, token_counting, vertexai, requirements]

# Dependency graph
requires:
  - phase: 04-streaming-migration
    provides: llm_client.count_tokens(model, text) and llm_client.DEFAULT_MODEL established
  - phase: 02-core-infrastructure
    provides: llm_client module with count_tokens, DEFAULT_MODEL, completion, completion_stream
provides:
  - answer_generator.py fully wired to llm_client for token counting (6 call sites)
  - MODEL env var never None — falls back to llm_client.DEFAULT_MODEL
  - requirements.txt free of dead openai/anthropic direct deps
  - .env.example documents LITELLM_MODEL and vertex_ai/ model format
affects: [answer_generator, requirements, onboarding]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "os.getenv('MODEL') or llm_client.DEFAULT_MODEL — always-valid model string pattern"
    - "llm_client.count_tokens(model, text) — model-first signature throughout all callers"

key-files:
  created: []
  modified:
    - fastcode/answer_generator.py
    - requirements.txt
    - .env.example

key-decisions:
  - "Remove count_tokens from utils import in answer_generator.py — fully routed through llm_client"
  - "MODEL fallback uses llm_client.DEFAULT_MODEL (not hardcoded string) — single source of truth"
  - "openai and anthropic removed from requirements.txt — no fastcode/ file imports them post-Phase 4"
  - ".env.example MODEL updated from placeholder to vertex_ai/ prefix example for new user clarity"

patterns-established:
  - "All 6 count_tokens call sites: llm_client.count_tokens(self.model, text) — model arg first"
  - "Model initialization: os.getenv('VAR') or llm_client.DEFAULT_MODEL — consistent with all migrated callers"

requirements-completed: [TOKN-01, STRM-01, STRM-02, STRM-03, CONF-01, CONF-02]

# Metrics
duration: 3min
completed: 2026-02-25
---

# Phase 5 Plan 01: Fix answer_generator.py Wiring and Cleanup Summary

**answer_generator.py fully wired to llm_client: 6 count_tokens call sites fixed with reversed arg order, MODEL=None runtime risk eliminated via DEFAULT_MODEL fallback, dead openai/anthropic deps removed, .env.example updated with vertex_ai/ model documentation**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T07:16:29Z
- **Completed:** 2026-02-25T07:19:03Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Fixed all 6 `count_tokens` call sites in answer_generator.py from `count_tokens(text, model)` to `llm_client.count_tokens(self.model, text)` — correct argument order matching llm_client API
- Eliminated MODEL=None runtime risk: `self.model = os.getenv("MODEL") or llm_client.DEFAULT_MODEL` ensures always-valid model string
- Removed `openai` and `anthropic` from requirements.txt (no fastcode/ files import them after Phase 4 migration)
- Updated `.env.example` with `LITELLM_MODEL=vertex_ai/gemini-2.0-flash-001` and corrected `MODEL` from placeholder to `vertex_ai/` example value

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix answer_generator.py — import line, 6 count_tokens call sites, MODEL fallback** - `744e47f` (fix)
2. **Task 2: Clean requirements.txt and update .env.example** - `15b51fa` (chore)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `fastcode/answer_generator.py` - Fixed import (removed count_tokens), MODEL fallback, all 6 count_tokens call sites
- `requirements.txt` - Removed openai and anthropic standalone entries
- `.env.example` - Updated MODEL with vertex_ai/ prefix example, added LITELLM_MODEL entry

## Decisions Made
- Remove `count_tokens` from utils import entirely — fully routed through `llm_client` module, consistent with all other migrated files
- `MODEL` fallback reads `llm_client.DEFAULT_MODEL` (not a hardcoded string) — single source of truth for the default model value
- `openai` and `anthropic` removed from `requirements.txt` — Phase 4 confirmed no fastcode/ file imports them; deferred removal is now safe
- `.env.example` MODEL updated from `your_model` placeholder to `vertex_ai/gemini-2.0-flash-001` example — guides new users to correct format

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 5 complete: all v1.0 audit gaps closed
- answer_generator.py fully integrated with litellm migration (Phases 1-4 infrastructure fully utilized)
- No remaining fastcode/ files using direct openai/anthropic imports
- New users guided to correct vertex_ai/ model format via .env.example

---
*Phase: 05-fix-answer-generator-wiring-and-cleanup*
*Completed: 2026-02-25*
