---
phase: 04-streaming-migration-and-finalization
plan: 01
subsystem: llm
tags: [litellm, llm_client, answer_generator, streaming, openai, anthropic]

# Dependency graph
requires:
  - phase: 02-core-infrastructure
    provides: llm_client module with completion() and completion_stream()
  - phase: 03-non-streaming-migration
    provides: Phase 3 migration pattern established across iterative_agent, repo_selector, repo_overview
provides:
  - fastcode/answer_generator.py fully migrated to llm_client with no provider-specific imports
  - llm_client.completion() used in generate()
  - llm_client.completion_stream() used in generate_stream() and _stream_with_summary_filter()
affects: [04-02-streaming-finalization, runtime-import-errors-eliminated]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "llm_client.completion(model=self.model, messages=[{role, content}], temperature, max_tokens) for non-streaming"
    - "llm_client.completion_stream() with raw_chunk.choices[0].delta.content or '' None-guard for streaming"
    - "Stream content extraction: chunk = raw_chunk.choices[0].delta.content or ''; if not chunk: continue"

key-files:
  created: []
  modified:
    - fastcode/answer_generator.py

key-decisions:
  - "os import kept — still needed for os.getenv('MODEL') in __init__"
  - "raw_response variable name preserved in generate() — used downstream for summary parsing in multi-turn mode"
  - "None-guard (or '' + if not chunk_text: continue) applied to both streaming loops per RESEARCH.md pitfall documentation"
  - "_stream_with_summary_filter() buffering and regex detection logic unchanged — only stream source replaced"
  - "chunk variable in _stream_with_summary_filter() is now plain string (same as before) so all buffer + chunk string operations work unchanged"

patterns-established:
  - "Stream iteration: for raw_chunk in stream_generator: chunk = raw_chunk.choices[0].delta.content or ''; if not chunk: continue"

requirements-completed: [STRM-01, STRM-02, STRM-03]

# Metrics
duration: 3min
completed: 2026-02-25
---

# Phase 4 Plan 01: answer_generator.py Migration Summary

**answer_generator.py migrated to llm_client with all three LLM dispatch sites (generate, generate_stream, _stream_with_summary_filter) replaced and provider-specific dead code deleted — runtime ImportError eliminated**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T00:08:50Z
- **Completed:** 2026-02-25T00:12:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Deleted all provider-specific code: `_initialize_client()`, `_generate_openai()`, `_generate_openai_stream()`, `_generate_anthropic()`, `_generate_anthropic_stream()` methods and `openai`/`anthropic`/`llm_utils` imports
- Replaced `generate()` provider dispatch with `llm_client.completion(model=self.model, ...)` with defensive response validation
- Replaced `generate_stream()` and `_stream_with_summary_filter()` provider dispatch with `llm_client.completion_stream()` and `raw_chunk.choices[0].delta.content or ""` None-guards
- Module now imports cleanly; no more ImportError on app startup from deleted llm_utils

## Task Commits

Each task was committed atomically:

1. **Task 1: Clean constructor and remove provider-specific imports and methods** - `c088fdc` (refactor)
2. **Task 2: Replace provider dispatch in generate(), generate_stream(), and _stream_with_summary_filter()** - `48c3971` (feat)

## Files Created/Modified
- `fastcode/answer_generator.py` - Migrated from openai/anthropic/llm_utils to llm_client; all three LLM dispatch sites replaced; 5 provider-specific methods deleted

## Decisions Made
- `os` import kept — still needed for `os.getenv("MODEL")` in `__init__`
- `raw_response` variable name preserved in `generate()` — used downstream for `_parse_response_with_summary()` in multi-turn mode
- None-guard (`or ""` + `if not chunk_text: continue`) applied to both streaming loops per documented litellm pitfall where `delta.content` can be `None`
- `_stream_with_summary_filter()` buffering and regex detection logic left entirely unchanged — variable `chunk` is now a plain string (same type as before), so all `buffer + chunk` string operations remain correct

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — straightforward mechanical replacement following the established Phase 3 migration pattern.

## Next Phase Readiness
- `answer_generator.py` is the last file that was importing from deleted `llm_utils` — the app's runtime ImportError is now eliminated
- `openai` and `anthropic` packages can be removed from `requirements.txt` (deferred to Phase 4 plan 02)
- `_stream_with_summary_filter()` chunk boundary behavior with litellm needs empirical testing — litellm may produce different chunk granularity vs Anthropic's original streaming

---
*Phase: 04-streaming-migration-and-finalization*
*Completed: 2026-02-25*
