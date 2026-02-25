# Phase 1: Config and Dependencies - Research

**Researched:** 2026-02-24
**Domain:** Python dependency management + LiteLLM VertexAI configuration + ADC authentication
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Version pinning:** Use minimum pin (`>=`) for `litellm[google]` in requirements.txt. Pin to whatever version is current at install time (e.g., `litellm[google]>=1.63.0`).
- **Smoke test:** Standalone pytest file: `tests/test_vertexai_smoke.py`. Test both paths:
  - Happy path: `litellm.completion("vertex_ai/gemini-3-flash-preview", ...)` returns a valid response using ADC
  - Error path: Without `VERTEXAI_PROJECT` set, produces a clear configuration error (not misleading 401)
- **Model targeting:** Validate against `vertex_ai/gemini-3-flash-preview` (not gemini-2.0-flash-001 from original roadmap)
- **Environment variable loading:** Load from `.env` file (python-dotenv or existing mechanism). Commit `.env.example` as template with all required vars: `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`, model name format. Add setup documentation. `.env` stays gitignored.

### Claude's Discretion

- Whether to add python-dotenv as new dependency or use existing env loading
- Exact pytest markers/fixtures for the smoke test
- Setup docs format (README section vs standalone file)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONF-01 | `requirements.txt` includes `litellm[google]` with version pin | `litellm[google]` installs `google-cloud-aiplatform>=1.38.0`. Latest stable version is 1.81.14. Pin as `litellm[google]>=1.63.0`. |
| CONF-02 | `.env.example` documents VertexAI vars: `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`, model name format | Confirmed env var names are `VERTEXAI_PROJECT` and `VERTEXAI_LOCATION`. Model format is `vertex_ai/gemini-3-flash-preview`. |
| CONF-04 | VertexAI works with ADC authentication (`gcloud auth application-default login`) | ADC is the correct path. No extra credentials file needed when using `gcloud auth application-default login`. |

</phase_requirements>

---

## Summary

Phase 1 is a pure infrastructure setup phase: add `litellm[google]` to `requirements.txt`, configure VertexAI environment variables, and write a smoke test that validates both the happy path (real API call via ADC) and the error path (clear failure when `VERTEXAI_PROJECT` is missing). No FastCode application code changes.

The critical finding is that `litellm[google]` is a real, supported extras group that installs exactly one dependency: `google-cloud-aiplatform>=1.38.0`. The `vertex_ai/` model prefix is the correct routing mechanism for ADC-based VertexAI — models without a prefix also route to VertexAI, but `gemini/` prefix routes to the Gemini API (simple API key, not ADC). The env var names are `VERTEXAI_PROJECT` and `VERTEXAI_LOCATION` (confirmed via Context7 and official litellm docs).

The project already has `python-dotenv` installed (`requirements.txt`) and `load_dotenv()` is already used in `answer_generator.py`, `query_processor.py`, and `repo_selector.py`. No new dependency needed — use the existing pattern. The smoke test must live in `tests/` (directory does not yet exist) and be runnable standalone via `pytest tests/test_vertexai_smoke.py`. The error-path test is the most nuanced: when `VERTEXAI_PROJECT` is not set, litellm's behavior needs to produce a recognizable configuration error rather than a misleading auth error. This may require the test to assert on exception type/message rather than validate exact behavior before the call.

**Primary recommendation:** Add `litellm[google]>=1.63.0` to `requirements.txt`, create `tests/` directory with the smoke test, update `env.example` to `.env.example` (the file is currently named `env.example` — no leading dot), and document the VertexAI setup.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `litellm` | `>=1.63.0` (current stable: 1.81.14) | Unified LLM client, routes `vertex_ai/` calls to VertexAI | Required for the entire migration; already in Nanobot |
| `google-cloud-aiplatform` | `>=1.38.0` (installed by `litellm[google]`) | VertexAI SDK, handles ADC token acquisition | Installed automatically via `litellm[google]` extra |
| `python-dotenv` | already in requirements.txt | Loads `.env` file into `os.environ` | Already used in project; no new dep needed |
| `pytest` | already in requirements.txt | Test runner for smoke test | Already used in project |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `google-auth` | transitive dep of `google-cloud-aiplatform` | ADC credential acquisition | Automatically pulled in; no explicit pin needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `litellm[google]` extras | `pip install google-cloud-aiplatform` separately | `litellm[google]` is the documented, canonical install that bundles both — prefer it |
| `VERTEXAI_PROJECT` env var | `litellm.vertex_project = "..."` in code | Env var is preferred for deployment hygiene; inline assignment is an option for tests |
| ADC via `gcloud auth application-default login` | Service account JSON (`GOOGLE_APPLICATION_CREDENTIALS`) | ADC is the chosen auth method (locked decision). Service account JSON is explicitly out of scope. |

**Installation:**
```bash
pip install "litellm[google]>=1.63.0"
```

---

## Architecture Patterns

### Recommended Project Structure

```
FastCode/
├── requirements.txt          # add litellm[google]>=1.63.0
├── .env.example              # rename from env.example + add VertexAI vars
├── .env                      # gitignored, local only
├── tests/                    # create new directory
│   └── test_vertexai_smoke.py
└── (no fastcode/ changes in Phase 1)
```

### Pattern 1: VertexAI Completion via ADC

**What:** Call `litellm.completion()` with `vertex_ai/` prefix — litellm reads `VERTEXAI_PROJECT` and `VERTEXAI_LOCATION` from environment and uses ADC for auth.

**When to use:** Standard production pattern for GCP-hosted workloads using `gcloud auth application-default login`.

**Example:**
```python
# Source: https://docs.litellm.ai/docs/providers/vertex + Context7 /berriai/litellm
import os
import litellm

os.environ["VERTEXAI_PROJECT"] = "your-gcp-project-id"
os.environ["VERTEXAI_LOCATION"] = "us-central1"
# Auth: gcloud auth application-default login (no explicit credential path needed)

response = litellm.completion(
    model="vertex_ai/gemini-3-flash-preview",
    messages=[{"role": "user", "content": "Hello"}],
)
print(response.choices[0].message.content)
```

### Pattern 2: Smoke Test — Happy Path + Error Path

**What:** pytest file that tests the full ADC-based round-trip AND the missing-config error behavior.

**When to use:** Run in isolation to validate infra before any app code changes.

**Example:**
```python
# Source: pattern from Context7 /berriai/litellm + pytest monkeypatch docs
import os
import pytest
import litellm
from dotenv import load_dotenv

load_dotenv()

VERTEX_MODEL = "vertex_ai/gemini-3-flash-preview"


class TestVertexAISmoke:
    """Smoke tests for VertexAI connection via ADC.

    Happy path requires real GCP credentials (VERTEXAI_PROJECT + ADC).
    Skip gracefully if not configured.
    """

    @pytest.mark.skipif(
        not os.environ.get("VERTEXAI_PROJECT"),
        reason="VERTEXAI_PROJECT not set — skipping live test"
    )
    def test_happy_path_returns_valid_response(self):
        """litellm.completion via vertex_ai/ returns a real response using ADC."""
        response = litellm.completion(
            model=VERTEX_MODEL,
            messages=[{"role": "user", "content": "Say hello in one word."}],
        )
        assert response.choices[0].message.content
        assert response.model is not None

    def test_missing_project_raises_config_error(self, monkeypatch):
        """Without VERTEXAI_PROJECT, error is a configuration error, not a 401."""
        monkeypatch.delenv("VERTEXAI_PROJECT", raising=False)
        monkeypatch.delenv("VERTEXAI_LOCATION", raising=False)

        with pytest.raises(Exception) as exc_info:
            litellm.completion(
                model=VERTEX_MODEL,
                messages=[{"role": "user", "content": "Hello"}],
            )

        # Error should be configuration-related, not an HTTP 401
        error_text = str(exc_info.value).lower()
        assert any(word in error_text for word in [
            "project", "credentials", "configuration", "not found", "default"
        ]), f"Expected config error, got: {exc_info.value}"
        assert "401" not in error_text, f"Got misleading 401: {exc_info.value}"
```

### Pattern 3: .env.example Template

**What:** Committed template documenting all required VertexAI vars.

```bash
# .env.example — copy to .env and fill in your values

# VertexAI / GCP Configuration
VERTEXAI_PROJECT=your-gcp-project-id
VERTEXAI_LOCATION=us-central1

# Model name format for litellm VertexAI calls:
# vertex_ai/gemini-3-flash-preview
# vertex_ai/gemini-2.0-flash-001
# (always use vertex_ai/ prefix for ADC-based auth)
VERTEXAI_MODEL=vertex_ai/gemini-3-flash-preview

# Existing FastCode vars (keep these)
OPENAI_API_KEY=your_openai_api_key_here
MODEL=your_model
BASE_URL=your_base_url
NANOBOT_MODEL=minimax/minimax-m2.1
```

### Anti-Patterns to Avoid

- **Using `gemini/` prefix for VertexAI:** `gemini/gemini-3-flash-preview` routes to Google AI Studio (requires `GEMINI_API_KEY`), NOT to VertexAI. Only `vertex_ai/` prefix uses ADC.
- **Using model without any prefix:** Bare model names like `gemini-3-flash-preview` also default to VertexAI but are ambiguous — always use the explicit `vertex_ai/` prefix for clarity.
- **Asserting exact error strings in the error-path test:** litellm's exact error messages change across versions. Assert on structural properties (exception type, presence of key words) rather than exact strings.
- **Putting tests that make live API calls in CI without guards:** Use `@pytest.mark.skipif` or environment-based skips so the happy-path test is a no-op when credentials are absent.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ADC token acquisition | Custom OAuth2 flow | `google-cloud-aiplatform` (via `litellm[google]`) | `google-auth` handles token refresh, expiry, workload identity — dozens of edge cases |
| VertexAI API request | Custom HTTP client to `aiplatform.googleapis.com` | `litellm.completion("vertex_ai/...")` | litellm handles request formatting, error translation, retry logic |
| Env var validation | Custom config checker | pytest test + `dotenv` | The smoke test IS the validation; no need for a separate validator module |

**Key insight:** The `litellm[google]` extras install exactly solves the "what do I need for VertexAI" question — it pulls in `google-cloud-aiplatform` which brings `google-auth`, the ADC chain, and the VertexAI REST client. Don't install these separately.

---

## Common Pitfalls

### Pitfall 1: Wrong model prefix routes to wrong provider

**What goes wrong:** Using `gemini/gemini-3-flash-preview` instead of `vertex_ai/gemini-3-flash-preview` causes litellm to route to Google AI Studio (Gemini API) instead of VertexAI. The error will demand `GEMINI_API_KEY`, not ADC credentials.

**Why it happens:** litellm uses the prefix before `/` as the provider key. `gemini/` = Gemini API, `vertex_ai/` = VertexAI. No prefix also defaults to VertexAI but is ambiguous.

**How to avoid:** Always use the `vertex_ai/` prefix explicitly. Document the format in `.env.example`.

**Warning signs:** Error mentions `GEMINI_API_KEY` when you expect ADC auth.

### Pitfall 2: `env.example` vs `.env.example` naming

**What goes wrong:** The current file is named `env.example` (no leading dot). The conventional name — and what `.gitignore` typically excludes — is `.env`. The example file should be `.env.example`.

**Why it happens:** The project was set up without the dot-prefix convention.

**How to avoid:** Rename `env.example` to `.env.example` during this phase. Verify `.gitignore` excludes `.env` but commits `.env.example`.

**Warning signs:** A `.env` created by copying `env.example` but named `.env` — check that `.gitignore` has a `.env` entry.

### Pitfall 3: Missing `VERTEXAI_PROJECT` produces unhelpful error

**What goes wrong:** When `VERTEXAI_PROJECT` is unset and no ADC credentials resolve a project, litellm/google-auth may surface a generic `DefaultCredentialsError` or a 401/403 that looks like a permissions issue, not a missing-config issue.

**Why it happens:** The Google auth library tries multiple credential sources (ADC, env, metadata server) and fails with a generic message when all fail. The project ID may or may not be required depending on how ADC was configured.

**How to avoid:** The error-path smoke test exists specifically to catch this. If it passes but produces an unhelpful error, the test needs to be tightened OR the smoke test should do a pre-flight check (`if not os.environ.get("VERTEXAI_PROJECT"): raise ConfigurationError(...)`) before calling litellm.

**Warning signs:** Running the smoke test without `VERTEXAI_PROJECT` and seeing `401 Unauthorized` or `403 Permission Denied` rather than something about project/configuration.

### Pitfall 4: `litellm[google]` vs plain `litellm` import

**What goes wrong:** `import litellm` works fine whether or not you installed the `[google]` extra. The extra is only needed at runtime when a `vertex_ai/` call actually happens. This means the CI/install step may appear to succeed, but calling `litellm.completion("vertex_ai/...")` fails at runtime with `ImportError` or `ModuleNotFoundError` if `google-cloud-aiplatform` is missing.

**Why it happens:** Python extras are optional dependencies. The base `litellm` package does not require `google-cloud-aiplatform`.

**How to avoid:** The smoke test's happy path (which makes a live call) will catch this. Also, `python -c "import google.cloud.aiplatform"` can be run as a quick import check.

**Warning signs:** `litellm` imports fine but `vertex_ai/` calls raise `ModuleNotFoundError: No module named 'google.cloud.aiplatform'`.

### Pitfall 5: `tests/` directory does not exist

**What goes wrong:** `pytest tests/test_vertexai_smoke.py` fails with `ERROR: not found: tests/test_vertexai_smoke.py` if the `tests/` directory has not been created.

**Why it happens:** The project currently has no `tests/` directory (confirmed by filesystem check).

**How to avoid:** Create `tests/__init__.py` (or just `tests/` directory) before or alongside the smoke test file.

---

## Code Examples

Verified patterns from official sources:

### Minimal VertexAI call with ADC (verified via Context7 + official docs)

```python
# Source: https://docs.litellm.ai/docs/providers/vertex + Context7 /berriai/litellm
import os
import litellm

os.environ["VERTEXAI_PROJECT"] = "your-project-id"
os.environ["VERTEXAI_LOCATION"] = "us-central1"
# Requires: gcloud auth application-default login

response = litellm.completion(
    model="vertex_ai/gemini-3-flash-preview",
    messages=[{"role": "user", "content": "Hello"}],
)
assert response.choices[0].message.content
```

### Setting project via litellm module attribute (alternative to env var)

```python
# Source: Context7 /berriai/litellm cookbook
import litellm

litellm.vertex_project = "your-project-id"
litellm.vertex_location = "us-central1"
```

### pytest monkeypatch for env var removal in error-path test

```python
# Source: pytest official docs
def test_missing_project_raises_config_error(self, monkeypatch):
    monkeypatch.delenv("VERTEXAI_PROJECT", raising=False)
    monkeypatch.delenv("VERTEXAI_LOCATION", raising=False)
    with pytest.raises(Exception):
        litellm.completion(model="vertex_ai/gemini-3-flash-preview", messages=[...])
```

### requirements.txt entry

```
# LLM Integration (replacing direct openai/anthropic clients)
litellm[google]>=1.63.0
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pip install google-cloud-aiplatform` separately | `pip install litellm[google]` installs it via extras | litellm ~1.0+ | Simpler — one install command, litellm manages the version constraint |
| `VERTEX_PROJECT` / `VERTEX_LOCATION` env vars | `VERTEXAI_PROJECT` / `VERTEXAI_LOCATION` | litellm evolved naming | Both names accepted per docs but `VERTEXAI_*` is the documented canonical form |
| Service account JSON (`GOOGLE_APPLICATION_CREDENTIALS`) | ADC via `gcloud auth application-default login` | GCP best practice evolution | ADC is simpler for dev/CI — no JSON file to manage |
| `gemini-3-flash-preview` model string | `vertex_ai/gemini-3-flash-preview` | litellm added prefix routing | Prefix makes provider intent explicit, removes ambiguity |

**Current litellm stable:** v1.81.14 (released 2026-02-20). Day-0 support for `gemini-3-flash-preview` was added in v1.80.8-stable.1.

**Deprecated/outdated:**
- `VERTEX_PROJECT` / `VERTEX_LOCATION`: Still works but `VERTEXAI_PROJECT` / `VERTEXAI_LOCATION` is the documented name — use the documented names.
- Bare `gemini-*` model names without prefix: Ambiguous, defaults to VertexAI but confusing — always use explicit prefix.

---

## Open Questions

1. **What exact error does litellm raise when `VERTEXAI_PROJECT` is unset with valid ADC?**
   - What we know: Google auth falls through a credential chain; project ID may come from ADC metadata or env var. If no project is found, `google.auth.exceptions.DefaultCredentialsError` or a `google.api_core` error is raised and wrapped by litellm as `APIConnectionError`.
   - What's unclear: Whether the wrapped error message is recognizable enough to assert on without exact string matching.
   - Recommendation: The smoke test should use broad keyword matching (`"project"`, `"credentials"`, `"default"`) rather than exact strings. If the test consistently produces a 401/403 instead, add a pre-flight guard that raises `ValueError("VERTEXAI_PROJECT is required")` before calling litellm.

2. **Does `gemini-3-flash-preview` require a specific minimum litellm version?**
   - What we know: Day-0 support was added in litellm v1.80.8-stable.1 (December 2025). The current stable is v1.81.14.
   - What's unclear: Whether the `>=1.63.0` pin (from the user's decision, presumably the version at discussion time) is sufficient or should be raised to `>=1.80.8`.
   - Recommendation: Raise the pin to `litellm[google]>=1.80.8` to guarantee `gemini-3-flash-preview` support. The user's `>=1.63.0` was a placeholder; the actual minimum for this model is higher.

3. **`env.example` rename: will git preserve history?**
   - What we know: `git mv env.example .env.example` preserves history. A delete + create loses it.
   - What's unclear: Whether the user cares about history for this file.
   - Recommendation: Use `git mv env.example .env.example` to rename; do not delete + recreate.

---

## Sources

### Primary (HIGH confidence)

- Context7 `/berriai/litellm` — VertexAI configuration, env var names, model string format, ADC setup
- Context7 `/websites/litellm_ai` — VertexAI pass-through docs, `DEFAULT_VERTEXAI_PROJECT` env var
- PyPI `litellm` JSON API — confirmed v1.81.14 is current stable; confirmed `litellm[google]` installs `google-cloud-aiplatform>=1.38.0`
- https://docs.litellm.ai/docs/providers/vertex — canonical VertexAI setup, env var names, model format
- https://docs.litellm.ai/docs/providers/gemini — confirmed `gemini/` prefix vs `vertex_ai/` prefix distinction

### Secondary (MEDIUM confidence)

- https://docs.litellm.ai/blog/gemini_3_flash — Day-0 support for `gemini-3-flash-preview` added in v1.80.8-stable.1
- https://docs.litellm.ai/release_notes/v1-81-14 — Confirmed v1.81.14 is the latest stable as of 2026-02-20
- https://cloud.google.com/vertex-ai/generative-ai/docs/start/gcp-auth — Google's ADC setup guide confirming `gcloud auth application-default login` is the recommended approach

### Tertiary (LOW confidence)

- GitHub issue BerriAI/litellm #14771 — illustrates `vertex_ai/` vs `gemini/` routing confusion (confirmed by docs, but issue details are anecdotal)
- GitHub issue BerriAI/litellm #10115 — illustrates service account format issues (not relevant to ADC path but useful context)

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — confirmed via PyPI API and Context7 official litellm docs
- Architecture: HIGH — env var names and model string format confirmed from multiple official sources
- Pitfalls: MEDIUM — prefix routing confusion confirmed; exact error behavior of missing `VERTEXAI_PROJECT` is LOW (not directly verified without running code)
- Error-path test behavior: LOW — the exact exception type/message when `VERTEXAI_PROJECT` is missing is not definitively documented; recommend empirical verification during implementation

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (litellm moves fast; check release notes before implementing if >2 weeks pass)
