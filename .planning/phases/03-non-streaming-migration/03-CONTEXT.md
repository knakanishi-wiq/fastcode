# Phase 3: Non-Streaming Migration - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate four Python files (`query_processor.py`, `iterative_agent.py`, `repo_overview.py`, `repo_selector.py`) away from direct `openai`/`anthropic` client usage to the centralized `llm_client` module. Phase ends when all four files contain no `openai`/`anthropic` imports and no provider dispatch branches. Behavior must be preserved end-to-end through VertexAI.

</domain>

<decisions>
## Implementation Decisions

### Migration Sequencing
- Migrate one file at a time — not all at once
- `query_processor.py` is migrated first (most critical code path)
- No fixed order for the remaining three files — let the planner assess and decide based on code analysis
- Each migrated file gets its own commit (one commit per file, not a single batched commit)

### Gemini System Message Handling
- Use litellm's built-in conversion — trust the abstraction layer to handle Gemini's lack of a `system` role
- Pass conversation history as-is to `llm_client`; do not pre-process or filter roles at the call site
- If a Gemini system message error occurs at runtime, fail hard with a clear error — do not silently degrade or retry without the system message
- Researcher must verify the exact litellm behavior for Gemini system messages before planning (confirm the adapter handles it correctly)

### Cleanup Depth
- Remove only what success criteria requires: direct provider imports (`openai`, `anthropic`) and provider dispatch branches (`if provider == "openai"`)
- Also remove function parameters that become unused after migration (e.g., `provider` args in function signatures) — dead parameters are confusing; update callers accordingly
- Check `requirements.txt` / `pyproject.toml` after migration — remove `openai` and `anthropic` packages if nothing else uses them after Phase 3

### Verification Approach
- After each file migration: static check (grep confirms banned imports absent) + smoke test (run existing test suite)
- No new tests written per migrated file — existing tests serve as the regression guard
- After all 4 files are migrated: manual end-to-end test — send a real query through the API and verify a valid response routes through VertexAI

### Claude's Discretion
- Order of the 3 remaining files after `query_processor.py`
- Exact grep commands / CI steps used for the static import check

</decisions>

<specifics>
## Specific Ideas

- The iterative agent multi-turn test in success criteria (#4) specifically checks for no Gemini system message errors — the researcher should confirm how litellm handles this and document the exact mechanism in RESEARCH.md so the planner knows what to rely on
- Cleanup of `provider` parameters may require updating call sites in other files — those callers should be updated in the same commit as the migrated file

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-non-streaming-migration*
*Context gathered: 2026-02-24*
