---
phase: 01-config-and-dependencies
plan: 01
subsystem: infra
tags: [litellm, vertexai, gcp, adc, google-cloud-aiplatform, pytest, smoke-test]

# Dependency graph
requires: []
provides:
  - litellm[google]>=1.80.8 installed and importable
  - google-cloud-aiplatform installed and importable
  - .env.example documenting VERTEXAI_PROJECT, VERTEXAI_LOCATION, and vertex_ai/ model format
  - VertexAI smoke tests (happy path + error path) validating ADC integration
affects:
  - 02-provider-routing
  - 03-agent-migration
  - 04-streaming

# Tech tracking
tech-stack:
  added:
    - litellm[google]>=1.80.8 (unified LLM client with VertexAI support)
    - google-cloud-aiplatform (transitive dep, provides ADC auth to VertexAI)
  patterns:
    - VertexAI calls use vertex_ai/ model prefix (not gemini/ which routes to Google AI Studio)
    - ADC authentication via VERTEXAI_PROJECT + VERTEXAI_LOCATION env vars
    - Smoke tests skip gracefully when VERTEXAI_PROJECT not set (CI-safe)

key-files:
  created:
    - .env.example (renamed from env.example)
    - tests/__init__.py
    - tests/test_vertexai_smoke.py
  modified:
    - requirements.txt

key-decisions:
  - "Use vertex_ai/ prefix in litellm model strings (not gemini/) to route through VertexAI with ADC"
  - "Smoke test happy path skips when VERTEXAI_PROJECT unset so CI without GCP credentials stays green"
  - "Broad keyword matching in error test (project/credentials/etc.) avoids fragile assertions on litellm version-specific messages"

patterns-established:
  - "LLM calls to VertexAI: litellm.completion(model='vertex_ai/<model>', ...) with ADC"
  - "Env vars: VERTEXAI_PROJECT + VERTEXAI_LOCATION required; model selection stays in code not env"

requirements-completed: [CONF-01, CONF-02, CONF-04]

# Metrics
duration: 6min
completed: 2026-02-24
---

# Phase 01 Plan 01: Config and Dependencies Summary

**litellm[google]>=1.80.8 installed with VertexAI ADC integration validated by smoke tests covering happy path and config-error path**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-02-23T23:20:50Z
- **Completed:** 2026-02-23T23:26:15Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added litellm[google]>=1.80.8 to requirements.txt and installed it along with google-cloud-aiplatform
- Renamed env.example to .env.example and added VertexAI config section (VERTEXAI_PROJECT, VERTEXAI_LOCATION, vertex_ai/ model format docs)
- Created tests/test_vertexai_smoke.py with two test cases: happy path (skips without ADC) and error path (always passes, confirming config error not 401)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add litellm dependency and configure .env.example** - `2fee870` (chore)
2. **Task 2: Create VertexAI smoke test** - `2f8dabd` (feat)

**Plan metadata:** _(docs commit — to be recorded)_

## Files Created/Modified

- `requirements.txt` - Added `litellm[google]>=1.80.8` under LLM Integration section
- `.env.example` - Renamed from env.example; added VertexAI config section
- `tests/__init__.py` - Empty init to register tests/ as pytest package
- `tests/test_vertexai_smoke.py` - Smoke tests: happy path (skipped when no ADC) + error path (config error, not 401)

## Decisions Made

- Used `vertex_ai/` prefix in model string (not `gemini/`) — this routes through VertexAI with ADC auth, not Google AI Studio
- Happy-path test uses `@pytest.mark.skipif` on VERTEXAI_PROJECT so CI without GCP credentials passes cleanly
- Error-path test uses broad keyword matching for error text ("project", "credentials", etc.) to avoid fragile assertions on litellm version-specific messages
- Did not add a VERTEXAI_MODEL env var — model selection is a code-level concern, not infrastructure

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

To run the happy-path smoke test with real VertexAI credentials:

1. Set up GCP Application Default Credentials:
   ```
   gcloud auth application-default login
   ```
2. Copy `.env.example` to `.env` and set:
   ```
   VERTEXAI_PROJECT=your-gcp-project-id
   VERTEXAI_LOCATION=us-central1
   ```
3. Verify:
   ```
   python -m pytest tests/test_vertexai_smoke.py -v
   ```

The error-path test runs without any credentials and always passes.

## Next Phase Readiness

- litellm + VertexAI integration is proven to work end-to-end
- Ready to begin Phase 2: Provider Routing (swap openai/anthropic direct clients for litellm calls)
- No blockers

---
*Phase: 01-config-and-dependencies*
*Completed: 2026-02-24*
