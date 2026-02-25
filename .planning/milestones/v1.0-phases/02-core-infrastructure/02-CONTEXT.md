# Phase 2: Core Infrastructure - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Create `fastcode/llm_client.py` — a centralized module that all FastCode LLM call sites import. Fix token counting so VertexAI model names don't raise KeyError. Delete `llm_utils.py` once llm_client covers its surface.

New capabilities (retry logic, observability, multi-provider dispatch) are out of scope for this phase.

</domain>

<decisions>
## Implementation Decisions

### Module interface
- `completion(model, messages, **kwargs)` — mirrors litellm signature directly; callers pass model string explicitly
- `completion_stream(model, messages, **kwargs)` — returns litellm streaming iterator directly (ModelResponseStream); callers iterate chunks themselves, no wrapping
- `count_tokens(model, text)` — exported from llm_client alongside completion functions; matches llm_utils.py signature for easy migration

### Configuration init
- litellm global settings (`drop_params=True`, `suppress_debug_info=True`) applied at module import time (module-level side effects); no explicit init() call required
- Default model reads from environment variable (`LITELLM_MODEL` or similar) when callers don't pass model=; callers will usually pass model= explicitly
- Validate `VERTEXAI_PROJECT` and `VERTEXAI_LOCATION` at import time — raise a clear, descriptive error immediately if missing; do not wait for first call

### Token counting behavior
- Try litellm's token_counter() first
- If litellm doesn't recognize the model (e.g. `vertex_ai/` prefix not in its registry), fall back to tiktoken `cl100k_base` tokenizer as a reasonable approximation
- `count_tokens(model, text)` signature — model arg kept so future dispatch (if needed) is possible

### Error handling
- Let litellm exceptions bubble up raw — no translation to FastCode-specific types
- No logging inside llm_client — completely silent on success and failure; callers own their logging

### Claude's Discretion
- Exact env var name for default model (`LITELLM_MODEL`, `FASTCODE_MODEL`, etc.)
- Whether to log a warning (not error) when falling back to cl100k for token counting
- Module docstring and inline comments

</decisions>

<specifics>
## Specific Ideas

- No specific references — open to standard litellm patterns (similar to Nanobot's `litellm_provider.py`)

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-core-infrastructure*
*Context gathered: 2026-02-24*
