# Architecture Patterns

**Domain:** LiteLLM provider migration for Python code intelligence backend
**Researched:** 2026-02-24
**Confidence:** HIGH (based on direct codebase analysis + Nanobot reference implementation)

---

## Current Architecture: What Exists Today

FastCode currently has **5 files** that instantiate direct provider clients (the PROJECT.md says 4, but `repo_overview.py` and `repo_selector.py` were missed in that count):

| File | Client Created | Call Method | Has Streaming |
|------|---------------|-------------|---------------|
| `fastcode/answer_generator.py` | `OpenAI()` or `Anthropic()` in `__init__` | `_generate_openai()`, `_generate_anthropic()` | Yes — `_generate_openai_stream()`, `_generate_anthropic_stream()` |
| `fastcode/query_processor.py` | `OpenAI()` or `Anthropic()` in `__init__` | `_call_openai()`, `_call_anthropic()` | No |
| `fastcode/iterative_agent.py` | `OpenAI()` or `Anthropic()` in `__init__` | `_call_llm()` (dispatches to openai/anthropic) | No |
| `fastcode/repo_selector.py` | `OpenAI()` or `Anthropic()` in `__init__` | `_call_openai()`, `_call_anthropic()` | No |
| `fastcode/repo_overview.py` | `OpenAI()` or `Anthropic()` in `__init__` | `openai_chat_completion()` only | No |

Each file independently: reads `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `BASE_URL` / `MODEL` env vars, initializes its own provider client in `__init__`, and dispatches via `if self.provider == "openai": ... elif self.provider == "anthropic": ...` branches.

`fastcode/llm_utils.py` is a thin utility that only handles the `max_tokens` / `max_completion_tokens` fallback for OpenAI-compatible APIs. It does not abstract the client itself.

`fastcode/utils.py` uses `tiktoken` for token counting — this must be replaced or made provider-aware since VertexAI models don't use tiktoken encodings.

---

## Recommended Architecture: Centralized LiteLLM Client

### Pattern: Single `LLMClient` Module

Replace per-file client initialization with a single `fastcode/llm_client.py` module that wraps litellm. All five files import from it.

**Why centralized over per-module:**
- The five files already share the same `provider`, `model`, `BASE_URL`, env var reading pattern — they are doing the same initialization 5x
- litellm configuration (drop_params, suppress_debug_info, VertexAI project/location) is global state that only needs to be set once
- Centralized error handling, logging, and retry logic in one place instead of five
- Nanobot's `LiteLLMProvider` class proves the pattern works; FastCode can use a simpler sync variant

### Component Diagram

```
.env / config.yaml
       |
       v
fastcode/llm_client.py          ← NEW: single LiteLLM wrapper
  - configure_litellm()           (called once at startup by FastCode.__init__)
  - completion(...)               (sync, non-streaming)
  - completion_stream(...)        (sync streaming generator)
       |
       |---- imported by ----+
       |                     |
       v                     v
answer_generator.py      query_processor.py
iterative_agent.py       repo_selector.py
repo_overview.py
```

### LiteLLM API Surface Used

litellm exposes `litellm.completion()` with an OpenAI-compatible signature. This replaces both the OpenAI and Anthropic call paths:

```python
# Non-streaming (replaces _call_openai, _call_anthropic, _generate_openai, _generate_anthropic)
import litellm

response = litellm.completion(
    model="vertex_ai/gemini-2.0-flash-001",   # or "openai/gpt-4o", "anthropic/claude-opus-4-5"
    messages=[{"role": "user", "content": prompt}],
    temperature=0.4,
    max_tokens=20000,
)
content = response.choices[0].message.content

# Streaming (replaces _generate_openai_stream, _generate_anthropic_stream)
response = litellm.completion(
    model="vertex_ai/gemini-2.0-flash-001",
    messages=[{"role": "user", "content": prompt}],
    stream=True,
)
for chunk in response:
    if chunk.choices and chunk.choices[0].delta.content:
        yield chunk.choices[0].delta.content
```

The streaming chunk iteration pattern is **identical to the existing OpenAI streaming loop** in `answer_generator.py` lines 682-685. This is the lowest-friction migration path.

---

## Component Boundaries After Migration

### `fastcode/llm_client.py` (NEW)

**Responsibility:** Single point of litellm configuration and invocation for all FastCode LLM calls.

**Contains:**
- `configure_litellm(config: Dict[str, Any])` — called once during `FastCode.__init__()`. Sets global litellm options (`drop_params=True`, `suppress_debug_info=True`) and validates VertexAI env vars.
- `completion(model, messages, temperature, max_tokens) -> str` — sync call, returns text content. Replaces all `_call_openai`, `_call_anthropic`, `_generate_openai`, `_generate_anthropic` methods.
- `completion_stream(model, messages, temperature, max_tokens) -> Generator[str, None, None]` — sync streaming generator. Replaces `_generate_openai_stream`, `_generate_anthropic_stream`.
- A module-level `_model` variable populated from `os.getenv("MODEL")` on import, so callers don't need to pass model explicitly.

**Does NOT contain:**
- Prompt building (stays in each component)
- Response parsing (stays in each component)
- Token counting (stays in `utils.py`, but `count_tokens` needs a provider-agnostic fallback)

**Communicates with:** All 5 LLM call-site files (answer_generator, query_processor, iterative_agent, repo_selector, repo_overview)

### `fastcode/answer_generator.py` (MODIFIED)

**Changes:**
- Remove `from openai import OpenAI`, `from anthropic import Anthropic`
- Remove `_initialize_client()`, `self.client`, `self.api_key`, `self.anthropic_api_key`, `self.base_url`
- Remove `_generate_openai()`, `_generate_anthropic()`, `_generate_openai_stream()`, `_generate_anthropic_stream()`
- Remove `if self.provider == "openai": ... elif self.provider == "anthropic":` dispatch in `generate()` and `generate_stream()`
- Add `from .llm_client import completion, completion_stream`
- Replace the four `_generate_*` private methods with two calls to `llm_client.completion()` and `llm_client.completion_stream()`
- Keep `_stream_with_summary_filter()` — it wraps any generator, provider-agnostic
- Keep streaming protocol: the `yield (chunk, None)` / `yield (None, metadata)` contract is unchanged

### `fastcode/query_processor.py` (MODIFIED)

**Changes:**
- Remove `OpenAI`, `Anthropic` imports and `_initialize_llm_client()`
- Remove `self.llm_client`, `self.api_key`, `self.anthropic_api_key`, `self.base_url`
- Remove `_call_openai()`, `_call_anthropic()`
- Replace with single `from .llm_client import completion` and use `completion(...)` directly in `_enhance_with_llm()` and `_resolve_references_and_rewrite()`

### `fastcode/iterative_agent.py` (MODIFIED)

**Changes:**
- Remove `OpenAI`, `Anthropic` imports, `_initialize_client()`, `self.client`
- Remove `if self.provider == "openai": ... elif self.provider == "anthropic":` in `_call_llm()`
- Replace `_call_llm()` body with `from .llm_client import completion`

### `fastcode/repo_selector.py` (MODIFIED)

**Changes:** Same pattern as query_processor — remove client init, replace `_call_openai`/`_call_anthropic` with `llm_client.completion()`.

### `fastcode/repo_overview.py` (MODIFIED)

**Changes:** Same pattern as repo_selector. Also uses `openai_chat_completion` — can be removed once litellm replaces the OpenAI client.

### `fastcode/llm_utils.py` (DELETED or KEPT EMPTY)

The current `openai_chat_completion()` wrapper exists solely to handle the `max_tokens` vs `max_completion_tokens` fallback for OpenAI models. litellm handles this internally via `drop_params=True`. This file can be deleted. Any imports of `openai_chat_completion` in the 5 files are removed as part of the migration.

### `fastcode/utils.py` — `count_tokens()` (MODIFIED)

`count_tokens()` uses `tiktoken.encoding_for_model(model)` which fails silently for non-OpenAI model names (e.g. `vertex_ai/gemini-2.0-flash-001`). litellm provides `litellm.token_counter()` which is provider-aware. Replace the tiktoken calls:

```python
# Before
import tiktoken
encoding = tiktoken.encoding_for_model(model)
return len(encoding.encode(text))

# After
import litellm
return litellm.token_counter(model=model, text=text)
```

litellm falls back to `cl100k_base` for unknown models, same behavior as current code. For VertexAI models it uses the correct tokenizer.

---

## Data Flow After Migration

### Initialization Flow

```
FastCode.__init__(config)
  → llm_client.configure_litellm(config)
      → reads MODEL, VERTEX_PROJECT, VERTEX_LOCATION from env
      → sets litellm.drop_params = True
      → sets litellm.suppress_debug_info = True
      → validates required env vars, logs warnings
  → AnswerGenerator.__init__(config)   [no longer init's own client]
  → QueryProcessor.__init__(config)    [no longer init's own client]
  → IterativeAgent.__init__(...)       [no longer init's own client]
  → RepositorySelector.__init__(...)   [no longer init's own client]
  → RepositoryOverviewGenerator(...)   [no longer init's own client]
```

### Query Flow (non-streaming)

```
user query
  → QueryProcessor.process()
      → llm_client.completion(model, messages)   [query rewriting/enhancement]
  → HybridRetriever.retrieve()
      → IterativeAgent (if enabled)
          → llm_client.completion(model, messages)   [confidence scoring + tool decisions]
  → AnswerGenerator.generate()
      → llm_client.completion(model, messages)   [answer generation]
  → Dict[str, Any] response
```

### Query Flow (streaming)

```
user query
  → [same as above through retrieval]
  → AnswerGenerator.generate_stream()
      → yield (None, metadata)
      → for chunk in llm_client.completion_stream(model, messages):
          → [_stream_with_summary_filter passes through unchanged]
          → yield (chunk, None)
      → yield (None, {"complete": True, ...})
```

### VertexAI Auth Flow

```
Docker container starts
  → ADC credentials available via:
      a) Mounted ~/.config/gcloud/application_default_credentials.json (local dev)
      b) GCP Workload Identity / service account (production)
  → litellm reads VERTEX_PROJECT_ID + VERTEX_LOCATION from env
  → litellm uses google-auth library with ADC automatically when model = "vertex_ai/..."
  → No API key required
```

---

## Patterns to Follow

### Pattern 1: Module-Level Configuration, Not Per-Instance

**What:** Configure litellm once at module level or startup. Do not pass a client object to every component.

**When:** litellm is designed as a module with global configuration. Per-class clients like the current OpenAI/Anthropic pattern do not apply.

**Example:**
```python
# fastcode/llm_client.py

import os
import litellm

litellm.drop_params = True
litellm.suppress_debug_info = True

_model: str = ""

def configure_litellm(config: dict) -> None:
    """Call once during FastCode.__init__(). Sets model and validates env."""
    global _model
    _model = os.getenv("MODEL", "")
    if not _model:
        raise ValueError("MODEL env var is required")
    # VertexAI: these env vars are read by litellm automatically
    # VERTEX_PROJECT, VERTEXAI_LOCATION (or VERTEX_LOCATION)
    if _model.startswith("vertex_ai/"):
        project = os.getenv("VERTEX_PROJECT") or os.getenv("VERTEXAI_PROJECT")
        if not project:
            import logging
            logging.getLogger(__name__).warning(
                "VERTEX_PROJECT not set; VertexAI calls will fail"
            )

def completion(messages: list, temperature: float, max_tokens: int) -> str:
    response = litellm.completion(
        model=_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content

def completion_stream(messages: list, temperature: float, max_tokens: int):
    response = litellm.completion(
        model=_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

### Pattern 2: Model Name as Full Provider-Prefixed String

**What:** Store model name as the fully-qualified litellm identifier. Never split provider and model into separate config fields.

**When:** Always. litellm routes on the model string prefix.

**Example:**
```
# .env
MODEL=vertex_ai/gemini-2.0-flash-001       # VertexAI
MODEL=anthropic/claude-opus-4-5            # Anthropic direct
MODEL=openai/gpt-4o                        # OpenAI direct
MODEL=openai/gpt-4o                        # OpenRouter (with BASE_URL set)
```

The `provider` field in `config.yaml` (`generation.provider: "openai"`) becomes irrelevant — remove it after migration. Provider is encoded in the model name.

### Pattern 3: Keep Streaming Contract Unchanged

**What:** `generate_stream()` in `answer_generator.py` yields `(chunk, None)` and `(None, metadata)` tuples. This protocol is consumed by `web_app.py` and `api.py` streaming endpoints. Do not change it.

**When:** The streaming generator internals change (litellm instead of openai/anthropic), but the yield protocol stays identical.

**Why this works:** litellm streaming chunks have the same structure as OpenAI streaming chunks (`chunk.choices[0].delta.content`). The replacement is drop-in at the chunk iteration level.

### Pattern 4: Token Counter Replacement

**What:** Replace `tiktoken` with `litellm.token_counter()` in `utils.py`.

**When:** Model names like `vertex_ai/gemini-2.0-flash-001` cause tiktoken to fall back to `cl100k_base` silently — accurate enough for truncation decisions, but misleading for logging. litellm's token counter is model-aware.

**Caveat (MEDIUM confidence):** litellm's token counter accuracy for VertexAI/Gemini models depends on the google-cloud-aiplatform library version. If it returns 0 or raises, fall back to `cl100k_base` like the current code does. Keep the try/except wrapper.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Per-Component litellm Import Without Central Configure

**What:** Each file imports litellm directly and calls `litellm.completion()` without any shared initialization.

**Why bad:** VertexAI project/location env vars need to be set and validated before the first call. Global litellm settings (`drop_params`, `suppress_debug_info`) would need to be repeated in every file. Error handling diverges.

**Instead:** Route all calls through `fastcode/llm_client.py`. The five call-site files import `from .llm_client import completion, completion_stream` only.

### Anti-Pattern 2: Preserving the `provider` Dispatch Pattern

**What:** Keeping `if self.provider == "openai": ... elif self.provider == "anthropic":` and replacing the OpenAI/Anthropic clients with `litellm.completion()` inside each branch.

**Why bad:** Defeats the purpose of litellm — you'd be calling litellm with a hardcoded provider prefix instead of letting the model string drive routing. Also leaves all the duplicated init code in place.

**Instead:** Delete all provider dispatch. Single `litellm.completion(model=_model, ...)` handles everything.

### Anti-Pattern 3: Wrapping Nanobot's `LiteLLMProvider` for FastCode Use

**What:** Re-using the async `LiteLLMProvider` from `nanobot/nanobot/providers/litellm_provider.py` in FastCode.

**Why bad:** Nanobot's provider is async (uses `acompletion`). FastCode's pipeline is synchronous — `generate()`, `generate_stream()`, `_call_llm()` are all sync. Using `asyncio.run()` to bridge would add latency and break streaming inside FastAPI's `StreamingResponse` context.

**Instead:** FastCode uses `litellm.completion()` (sync) directly. Nanobot continues using `litellm.acompletion()` (async). They are separate usage patterns of the same library.

### Anti-Pattern 4: Removing tiktoken Before Verifying Fallback

**What:** Deleting tiktoken from requirements.txt immediately.

**Why bad:** `count_tokens()` in `utils.py` is called during prompt truncation before every LLM call. If litellm's token counter fails for any reason, there's no fallback, and truncation silently breaks.

**Instead:** Migrate `count_tokens()` to use `litellm.token_counter()` with a `try/except` that falls back to `tiktoken.get_encoding("cl100k_base")`. Keep tiktoken in requirements.txt until the litellm path is verified in production.

---

## Build Order (Implementation Phases)

The dependency structure dictates this order:

**Step 1 — Create `fastcode/llm_client.py`**
No existing code changes. Pure addition. Can be tested in isolation.

**Step 2 — Migrate `fastcode/utils.py` `count_tokens()`**
Token counting is used by `answer_generator.py` before LLM calls. Fix this before migrating the generators or truncation logic breaks with VertexAI model names.

**Step 3 — Migrate `fastcode/llm_utils.py` → deprecate**
Remove `openai_chat_completion` dependency from all 5 files. This import is in answer_generator, query_processor, iterative_agent, repo_selector, repo_overview.

**Step 4 — Migrate non-streaming callers first** (lower risk)
Order: `repo_overview.py` → `repo_selector.py` → `query_processor.py` → `iterative_agent.py`
These are all non-streaming, single-call patterns. Each is an isolated change: remove init, replace `_call_openai`/`_call_anthropic` with `llm_client.completion()`.

**Step 5 — Migrate `answer_generator.py`** (highest risk, last)
This file has both streaming and non-streaming paths, plus the `_stream_with_summary_filter()` buffering logic. Migrate non-streaming `generate()` first, then `generate_stream()`. The `_stream_with_summary_filter()` method is provider-agnostic and requires no changes.

**Step 6 — Update `requirements.txt` and `.env`**
Add `litellm`, add `google-cloud-aiplatform` (required for VertexAI). Remove `openai` and `anthropic` (or keep as optional). Add VertexAI env var documentation.

**Step 7 — Update `config/config.yaml`**
Remove `generation.provider` field (now encoded in MODEL env var). Add comments showing model name format examples.

---

## Integration Points Between litellm and Existing Components

| Integration Point | Current | After Migration |
|------------------|---------|----------------|
| Client init at startup | `OpenAI(api_key=...)` in each `__init__` | `llm_client.configure_litellm(config)` in `FastCode.__init__()` |
| Non-streaming call | `client.chat.completions.create(...)` or `client.messages.create(...)` | `litellm.completion(model=_model, ...)` |
| Streaming call | `client.chat.completions.create(stream=True)` | `litellm.completion(model=_model, stream=True)` |
| Chunk iteration | `chunk.choices[0].delta.content` | Identical — `chunk.choices[0].delta.content` |
| VertexAI auth | N/A (not supported) | ADC via google-auth, zero code required |
| Token counting | `tiktoken.encoding_for_model(model)` | `litellm.token_counter(model=model, text=text)` |
| Model routing | `generation.provider` in config.yaml | Model name prefix (`vertex_ai/`, `openai/`, `anthropic/`) |
| OpenRouter/Ollama | `BASE_URL` env var → `OpenAI(base_url=...)` | litellm handles OpenAI-compatible endpoints via `openai/` prefix + `api_base` |

---

## VertexAI Environment Variables

Based on litellm documentation patterns and the Nanobot provider's `_setup_env()` for gateway routing:

```bash
# Required for VertexAI
MODEL=vertex_ai/gemini-2.0-flash-001   # or any vertex_ai/* model
VERTEX_PROJECT=my-gcp-project-id        # GCP project ID
VERTEXAI_LOCATION=us-central1           # or VERTEX_LOCATION

# Auth: no API key needed — use ADC
# Local: gcloud auth application-default login
# GCP: service account or workload identity provides ADC automatically

# Optional: keep existing providers working
# OPENAI_API_KEY=...
# ANTHROPIC_API_KEY=...
# BASE_URL=...   (for OpenRouter/Ollama)
```

litellm reads `VERTEX_PROJECT` and `VERTEXAI_LOCATION` (or `VERTEX_LOCATION`) as env vars automatically when the model is prefixed with `vertex_ai/`. No additional configuration code is needed beyond setting these env vars.

**Confidence note:** The exact env var names (`VERTEX_PROJECT` vs `VERTEXAI_PROJECT`) should be verified against the litellm docs before implementation. litellm has had minor naming inconsistencies across versions.

---

## Scalability Considerations

| Concern | Current | With LiteLLM |
|---------|---------|-------------|
| Provider switching | Code change + redeploy | Change `MODEL` env var + restart |
| Adding new provider | New client class, new dispatch branch in 5 files | Change model name prefix only |
| Retry/fallback | None | litellm has built-in retry + fallback to backup models via `fallbacks=[...]` |
| Rate limiting | Handled per-provider | litellm has provider-aware rate limit handling |
| Token counting accuracy | tiktoken (OpenAI-only) | litellm model-aware, falls back gracefully |

---

## Files Requiring Changes (Summary)

| File | Change Type | Risk |
|------|------------|------|
| `fastcode/llm_client.py` | CREATE | Low — new file |
| `fastcode/utils.py` | MODIFY — `count_tokens()`, `truncate_to_tokens()` | Low — isolated utility |
| `fastcode/llm_utils.py` | DELETE | Low — import removed from all callers first |
| `fastcode/repo_overview.py` | MODIFY — remove client init, replace calls | Low — no streaming |
| `fastcode/repo_selector.py` | MODIFY — remove client init, replace calls | Low — no streaming |
| `fastcode/query_processor.py` | MODIFY — remove client init, replace calls | Low — no streaming |
| `fastcode/iterative_agent.py` | MODIFY — remove client init, replace `_call_llm()` | Medium — large file, many LLM calls |
| `fastcode/answer_generator.py` | MODIFY — remove client init, replace 4 generate methods | High — streaming + non-streaming |
| `requirements.txt` | MODIFY — add litellm, google-cloud-aiplatform | Low |
| `config/config.yaml` | MODIFY — remove provider field, add model format docs | Low |
| `.env` / `.env.example` | MODIFY — add VERTEX_PROJECT, VERTEXAI_LOCATION | Low |

---

## Sources

- Direct codebase analysis: `fastcode/answer_generator.py`, `fastcode/query_processor.py`, `fastcode/iterative_agent.py`, `fastcode/repo_selector.py`, `fastcode/repo_overview.py`, `fastcode/llm_utils.py`, `fastcode/utils.py` (HIGH confidence)
- Reference implementation: `nanobot/nanobot/providers/litellm_provider.py` (HIGH confidence — same codebase)
- litellm streaming chunk format: same as OpenAI SDK format, verified by inspection of existing streaming code in `answer_generator.py` lines 682-685 (HIGH confidence)
- VertexAI env var names: inferred from litellm docs patterns and community usage; verify exact names before implementation (MEDIUM confidence)
- `litellm.token_counter()` fallback behavior for unknown models: inferred from litellm's documented fallback to cl100k_base; verify accuracy for Gemini models (MEDIUM confidence)

---

*Architecture analysis: 2026-02-24*
