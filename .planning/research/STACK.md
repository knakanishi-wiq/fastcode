# Technology Stack

**Project:** FastCode — LiteLLM + VertexAI Provider Migration
**Researched:** 2026-02-24
**Milestone:** Replace direct openai/anthropic clients with litellm; enable VertexAI via GCP ADC

---

## Recommended Stack

### Core LLM Abstraction

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `litellm` | `>=1.61.0` (latest stable: 1.81.14) | Unified LLM client replacing openai + anthropic | Battle-tested, supports 100+ providers, zero-config VertexAI via `vertex_ai/` prefix, streaming-compatible, already used in Nanobot |

**Confidence: HIGH** — Version verified via PyPI JSON API. LiteLLM is already a declared dependency in `nanobot/pyproject.toml` (`litellm>=1.0.0`).

### VertexAI Extra Dependency

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `google-cloud-aiplatform` | `>=1.38.0` | VertexAI client library for litellm's `google` extra | Required when litellm calls VertexAI. The litellm `google` extra installs this automatically |

**Confidence: HIGH** — Confirmed via litellm `pyproject.toml` (`extras = { google = ["google-cloud-aiplatform>=1.38.0"] }`) and PyPI metadata.

**Install command:**
```bash
pip install "litellm[google]>=1.61.0"
```

> Note: `google-cloud-aiplatform` version 1.138.0 is the current latest as of 2026-02-24. The `>=1.38.0` floor means any current version satisfies the constraint.

### Token Counting

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `tiktoken` | `>=0.7.0` | Approximate token counting for context window management | Already in use in `fastcode/utils.py`. litellm ships with tiktoken as a core dependency. No change needed — tiktoken is the correct fallback for Gemini/VertexAI models where a native tokenizer is unavailable |

**Confidence: HIGH** — Verified via litellm source: `token_counter()` falls back to tiktoken for Gemini/VertexAI models (no native Gemini tokenizer path in litellm as of 2026). `count_tokens()` in `fastcode/utils.py` already handles `KeyError` gracefully with `cl100k_base` fallback, which is appropriate for Gemini models.

**Key behavior to document:** For VertexAI Gemini models, `tiktoken.encoding_for_model("gemini-2.0-flash")` will raise `KeyError`, causing `count_tokens()` to fall through to `cl100k_base`. This gives approximate but workable counts — acceptable for context budget management, not billing.

### GCP Auth (No New Dependency)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `google-auth` | `>=2.47.0` (transitive via `google-cloud-aiplatform`) | Application Default Credentials (ADC) | litellm calls `google.auth.default()` automatically when `VERTEXAI_CREDENTIALS` is not set. ADC works with `gcloud auth application-default login` locally and with the default service account in GCP. No explicit import needed in FastCode code |

**Confidence: HIGH** — Verified in litellm `vertex_llm_base.py`: ADC is the documented fallback auth path when no `VERTEXAI_CREDENTIALS` env var is present.

---

## Packages to Remove

| Package | Reason | Replaced By |
|---------|--------|-------------|
| `openai` | Direct client usage replaced by litellm | `litellm.completion()` with model prefix (e.g. `openai/gpt-4o`) |
| `anthropic` | Direct client usage replaced by litellm | `litellm.completion()` with model prefix (e.g. `anthropic/claude-sonnet-4-5`) |

> **Caveat:** litellm itself declares `openai>=1.61.0` as a core dependency. The `openai` package will remain installed transitively. The distinction is that FastCode's code no longer directly imports `OpenAI` or `Anthropic` client classes — all calls go through litellm.

---

## VertexAI Configuration Patterns

### Environment Variables

| Variable | Required | Example Value | Notes |
|----------|----------|---------------|-------|
| `VERTEXAI_PROJECT` | Yes | `my-gcp-project-id` | GCP project ID. litellm enforces `isinstance(str)` — cannot be numeric |
| `VERTEXAI_LOCATION` | No | `us-central1` | Defaults to `us-central1` if unset. Some global-only models override to `global` |
| `VERTEXAI_CREDENTIALS` | No | `/path/to/creds.json` or JSON string | **Leave unset for ADC**. Set only when using a service account JSON file explicitly |
| `MODEL` | Yes | `vertex_ai/gemini-2.0-flash-001` | Replaces existing `MODEL` env var. Must use `vertex_ai/` prefix |

**Confidence: HIGH** — Verified in litellm `vertex_llm_base.py` source.

### Model Name Format

Use the `vertex_ai/` prefix followed by the Vertex AI model ID:

```
vertex_ai/gemini-2.0-flash-001          # Gemini 2.0 Flash (recommended: fast, cheap)
vertex_ai/gemini-2.0-flash-lite-001     # Gemini 2.0 Flash Lite (lightest option)
vertex_ai/gemini-1.5-pro-002            # Gemini 1.5 Pro (large context, capable)
vertex_ai/gemini-1.5-flash-002          # Gemini 1.5 Flash (balanced)
vertex_ai/gemini-2.5-pro-preview-0325   # Gemini 2.5 Pro Preview (most capable, 2026)
```

**Confidence: MEDIUM** — Model IDs from Google Vertex AI documentation patterns and litellm prefix convention (`vertex_ai/` confirmed HIGH). Specific model ID strings should be validated against active GCP project before deployment.

### Module-Level Config (Alternative to Env Vars)

```python
import litellm

# Set project/location programmatically (alternative to env vars)
litellm.vertex_project = "my-gcp-project-id"
litellm.vertex_location = "us-central1"

# Silence litellm debug noise
litellm.suppress_debug_info = True
litellm.drop_params = True  # Drop unsupported params gracefully
```

**Confidence: HIGH** — `vertex_project` and `vertex_location` verified as module-level attributes in litellm `__init__.py`. `drop_params` behavior verified in Nanobot's `litellm_provider.py` (line 50).

---

## litellm API Patterns for FastCode

### Non-Streaming (replaces `openai_chat_completion` and `anthropic.messages.create`)

```python
import litellm

response = litellm.completion(
    model="vertex_ai/gemini-2.0-flash-001",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.4,
    max_tokens=20000,
)
content = response.choices[0].message.content
```

**Confidence: HIGH** — Standard litellm OpenAI-compatible interface.

### Streaming (replaces `_generate_openai_stream` and `_generate_anthropic_stream`)

```python
import litellm

response = litellm.completion(
    model="vertex_ai/gemini-2.0-flash-001",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.4,
    max_tokens=20000,
    stream=True,
)
for chunk in response:
    if chunk.choices and chunk.choices[0].delta.content:
        yield chunk.choices[0].delta.content
```

**Confidence: HIGH** — `stream=True` returns `CustomStreamWrapper`, same iteration pattern as OpenAI SDK streaming. Verified in litellm `main.py` — return type is `Union[ModelResponse, CustomStreamWrapper]`.

### Async Completion (if needed)

```python
from litellm import acompletion

response = await acompletion(
    model="vertex_ai/gemini-2.0-flash-001",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=20000,
)
```

**Confidence: HIGH** — `acompletion` is the async variant, already used in Nanobot's `litellm_provider.py` (line 8).

---

## What NOT to Use

| What | Why Not |
|------|---------|
| `litellm.Router` | Overkill for single-provider migration. Router adds load balancing/fallback logic not needed here |
| `LiteLLM Proxy Server` (Docker sidecar) | Not needed — direct Python SDK calls are sufficient for FastCode's use case |
| `google-generativeai` (AI Studio SDK) | This is the AI Studio client, not VertexAI. Using it bypasses ADC and GCP infra entirely |
| `vertexai.generative_models` | The direct VertexAI Python SDK. Deprecated as of June 24, 2025 (removal June 2026). litellm abstracts this correctly |
| `GOOGLE_APPLICATION_CREDENTIALS` env var | This is a generic GCP env var, not VertexAI-specific. litellm prefers `VERTEXAI_CREDENTIALS`. Using the wrong var causes silent auth failures |

**Confidence: HIGH** for all above — Router/Proxy pattern based on litellm docs; deprecation of `vertexai.generative_models` confirmed via `google-cloud-aiplatform` PyPI metadata (deprecation note on `vertexai.generative_models.*` as of June 2025).

---

## Installation

### requirements.txt Changes

Remove:
```
openai
anthropic
```

Add:
```
litellm[google]>=1.61.0
```

> `tiktoken` is already in requirements.txt and stays — it is also a litellm core dependency so there is no conflict.

### Full install (dev):
```bash
pip install "litellm[google]>=1.61.0"
```

### Docker (production):
No Dockerfile changes needed beyond `requirements.txt`. GCP credentials in Docker:
- **Local dev:** Mount `~/.config/gcloud/application_default_credentials.json` as a volume
- **GCP (GKE/Cloud Run):** Uses default service account automatically — no credential mount needed
- **docker-compose env:** Set `VERTEXAI_PROJECT` and `VERTEXAI_LOCATION` in environment block

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| LLM Abstraction | `litellm` | `langchain` LLM wrappers | LangChain adds significant dependency weight and opinionated abstractions incompatible with FastCode's direct prompt approach |
| LLM Abstraction | `litellm` | Custom thin wrapper | litellm already proven in Nanobot; maintaining a custom wrapper duplicates work already done |
| Auth | ADC (no credentials file) | Service Account JSON in `VERTEXAI_CREDENTIALS` | ADC is zero-config in GCP (Cloud Run, GKE). SA JSON requires credential file management |
| Model | `vertex_ai/gemini-2.0-flash-001` | `vertex_ai/gemini-1.5-pro-002` | Flash is sufficient for code Q&A, dramatically cheaper and faster. Pro adds value only for very long contexts (>200K tokens) |
| Token Counting | `tiktoken` (keep as-is) | `litellm.token_counter()` | `count_tokens()` in `fastcode/utils.py` already handles the fallback pattern correctly. Migrating to `litellm.token_counter()` is optional — it uses tiktoken as its own fallback for Gemini, so results are identical |

---

## Sources

- litellm PyPI (version 1.81.14): https://pypi.org/pypi/litellm/json — HIGH confidence
- litellm `pyproject.toml` (google extra): https://raw.githubusercontent.com/BerriAI/litellm/main/pyproject.toml — HIGH confidence
- litellm `__init__.py` (vertex_project, vertex_location, drop_params): https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/__init__.py — HIGH confidence
- litellm `vertex_llm_base.py` (auth patterns, env vars): https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/llms/vertex_ai/vertex_llm_base.py — HIGH confidence
- litellm `main.py` (streaming, token_counter): https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/main.py — HIGH confidence
- litellm `utils.py` (token_counter tiktoken fallback for Gemini): https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/utils.py — HIGH confidence
- google-cloud-aiplatform PyPI (deprecation notice, version 1.138.0): https://pypi.org/pypi/google-cloud-aiplatform/json — HIGH confidence
- Nanobot `litellm_provider.py` (patterns reference): `/Users/knakanishi/Repositories/FastCode/nanobot/nanobot/providers/litellm_provider.py` — HIGH confidence (codebase)
- Nanobot `pyproject.toml` (`litellm>=1.0.0`): `/Users/knakanishi/Repositories/FastCode/nanobot/pyproject.toml` — HIGH confidence (codebase)
