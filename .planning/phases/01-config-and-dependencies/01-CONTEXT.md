# Phase 1: Config and Dependencies - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Install litellm with Google extras, configure VertexAI environment variables, and validate that ADC-based connections work with a smoke test. No FastCode application code is modified in this phase.

</domain>

<decisions>
## Implementation Decisions

### Version pinning
- Use minimum pin (`>=`) for `litellm[google]` in requirements.txt
- Pin to whatever version is current at install time (e.g., `litellm[google]>=1.63.0`)
- Allows patch and minor updates through automatically

### Smoke test
- Standalone pytest file: `tests/test_vertexai_smoke.py`
- Test both paths:
  - Happy path: `litellm.completion("vertex_ai/gemini-3-flash-preview", ...)` returns a valid response using ADC
  - Error path: Without `VERTEXAI_PROJECT` set, produces a clear configuration error (not misleading 401)
- Should be runnable in isolation: `pytest tests/test_vertexai_smoke.py`

### Model targeting
- Validate against `vertex_ai/gemini-3-flash-preview` (not gemini-2.0-flash-001 from original roadmap)
- This is the model string format used throughout the migration

### Environment variable loading
- Load from `.env` file (python-dotenv or existing mechanism)
- Commit `.env.example` as template with all required vars: `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`, model name format
- Add setup documentation (README section or SETUP.md) covering env var configuration
- `.env` stays gitignored

### Claude's Discretion
- Whether to add python-dotenv as new dependency or use existing env loading
- Exact pytest markers/fixtures for the smoke test
- Setup docs format (README section vs standalone file)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-config-and-dependencies*
*Context gathered: 2026-02-24*
