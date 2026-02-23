# Feature Landscape

**Domain:** LLM provider abstraction layer migration (litellm + VertexAI)
**Researched:** 2026-02-24
**Confidence:** MEDIUM (core litellm API: HIGH from Nanobot reference impl + training; VertexAI specifics: MEDIUM — official docs unavailable during research, verified patterns from nanobot/nanobot/providers/litellm_provider.py)

---

## Table Stakes

Features that must work or the migration is broken. Each maps to an existing call site in the codebase.

| Feature | Why Expected | Complexity | Call Site | Notes |
|---------|--------------|------------|-----------|-------|
| `litellm.completion()` sync call | Replaces `openai.chat.completions.create()` and `anthropic.messages.create()` in answer_generator.py and query_processor.py | Low | `answer_generator._generate_openai()`, `answer_generator._generate_anthropic()`, `query_processor._call_openai()`, `query_processor._call_anthropic()` | litellm returns OpenAI-compatible response objects; `response.choices[0].message.content` works unchanged |
| `litellm.completion(..., stream=True)` streaming | `answer_generator.generate_stream()` and `_stream_with_summary_filter()` both iterate over streaming chunks; must preserve `chunk.choices[0].delta.content` pattern | Medium | `answer_generator._generate_openai_stream()`, `answer_generator._generate_anthropic_stream()` | The existing OpenAI streaming chunk shape is preserved by litellm; Anthropic's `stream.text_stream` pattern must be replaced with the OpenAI-compatible chunk iterator |
| `vertex_ai/` model prefix for VertexAI routing | litellm routes to VertexAI when model is prefixed `vertex_ai/` (e.g. `vertex_ai/gemini-1.5-pro`) | Low | All 4 call sites — model name set via `os.getenv("MODEL")` | Requires no code change to call sites; only env var `MODEL=vertex_ai/gemini-1.5-pro` |
| ADC authentication (no explicit API key) | VertexAI uses Application Default Credentials; litellm respects ADC natively for `vertex_ai/` models when no explicit key passed | Low | `_initialize_client()` in answer_generator.py, query_processor.py, iterative_agent.py | `VERTEXAI_PROJECT` and `VERTEXAI_LOCATION` env vars required; no `api_key` param needed |
| `VERTEXAI_PROJECT` + `VERTEXAI_LOCATION` env vars | litellm reads these to construct VertexAI endpoint; replaces `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` for VertexAI | Low | `.env` file and Docker config | Existing `BASE_URL` env var no longer needed for VertexAI |
| `max_tokens` parameter pass-through | `answer_generator.py` passes `max_tokens=20000`; `iterative_agent.py` passes `max_tokens=6000`; must reach VertexAI model | Low | All 4 call sites | litellm passes `max_tokens` to all providers; VertexAI models use this correctly |
| `temperature` parameter pass-through | Set to 0.4 (answer generation), 0.3 (query processing), 0.2 (agent) — must reach VertexAI | Low | All 4 call sites | Standard parameter, litellm forwards to all providers |
| OpenAI-compatible response object | Existing code accesses `response.choices[0].message.content` — litellm must return this shape | Low | `answer_generator._generate_openai()`, `query_processor._call_openai()` | litellm normalizes all provider responses to OpenAI format; confirmed by Nanobot's `_parse_response()` using same pattern |
| `litellm.drop_params = True` | Some VertexAI models reject unknown parameters; prevents `BadRequestError`-equivalent crashes | Low | Global config at startup | Already used in Nanobot's `LiteLLMProvider.__init__()` — must carry to FastCode |
| Remove `openai` + `anthropic` direct client init | `_initialize_client()` in 3 files creates `OpenAI(...)` or `Anthropic(...)` objects — these must be removed entirely | Medium | `answer_generator.py`, `query_processor.py`, `iterative_agent.py` | No wrapper object needed; litellm functions are called directly with model name |

## Feature Dependencies

```
ADC authentication → VERTEXAI_PROJECT + VERTEXAI_LOCATION env vars
vertex_ai/ prefix → ADC authentication (prefix tells litellm which auth to use)
litellm.completion() sync → Remove direct client init
litellm.completion(stream=True) → Preserve chunk.choices[0].delta.content iteration pattern
litellm.drop_params → Global config at startup (before any LLM call)
```

---

## Differentiators

Features litellm provides beyond the minimum migration requirement. These are available without extra code but should be consciously decided about.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `litellm.token_counter(model, messages)` | Replaces `tiktoken.encoding_for_model()` used in `fastcode/utils.py`; works for VertexAI model names that tiktoken doesn't know | Medium | Currently `count_tokens()` in `utils.py` uses tiktoken — will fail with `vertex_ai/gemini-1.5-pro` because tiktoken has no Gemini tokenizer. litellm token_counter is model-aware. This is actually a table-stakes dependency that gets promoted to differentiator because the fix is in a separate file |
| `litellm.acompletion()` async version | FastCode is synchronous today but FastAPI runs in async context; using `acompletion` would unblock the event loop during LLM calls | High | Out of scope for this migration (sync-to-async is a separate refactor), but available if desired. Nanobot uses `acompletion` exclusively |
| Provider fallback / retry config | `litellm.completion()` supports `fallbacks=[...]` and `num_retries=3`; auto-retries on rate limit or transient errors | Medium | Not needed for initial migration but reduces operational fragility without code changes |
| `litellm.success_callback` / `litellm.failure_callback` | Hooks for logging every LLM call cost, token usage, and latency to external systems | Medium | Useful for observability in GCP; not needed for migration |
| Budget tracking via `litellm.max_budget` | Prevent runaway costs in GCP; set a per-session or global token/cost limit | Low | Relevant for production GCP deployment |
| `litellm.suppress_debug_info = True` | Disables noisy default litellm logging output | Low | Should be set at startup; already in Nanobot reference impl |
| Model aliasing via `litellm.model_alias_map` | Map `gpt-4` → `vertex_ai/gemini-1.5-pro` in one place; existing code passes model name from env var so this is largely irrelevant | Low | Not needed given env-var-driven model selection |

---

## Anti-Features

Things to explicitly NOT build or enable during this migration.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| litellm Proxy server | litellm has an optional HTTP proxy server mode (`litellm --port 8000`); it is a separate deployment concern that adds infra complexity | Use litellm as a Python library only (`import litellm`) — same as Nanobot does |
| Custom `LLMProvider` wrapper class | Tempting to build an abstraction layer on top of litellm (like Nanobot's `LiteLLMProvider`); adds indirection with no benefit in FastCode's simpler synchronous call pattern | Call `litellm.completion()` directly at each call site |
| OpenAI compatibility shim / `openai` SDK kept alongside litellm | Keeping `from openai import OpenAI` alongside litellm creates two code paths and contradicts the migration goal | Remove `openai` and `anthropic` imports entirely from the 4 affected files after migration |
| `BASE_URL` env var for VertexAI | The existing `BASE_URL` pattern was for OpenRouter/Ollama; VertexAI does not use a custom base URL — litellm constructs it from `VERTEXAI_PROJECT` + `VERTEXAI_LOCATION` | Remove `BASE_URL` from VertexAI config; document it as OpenRouter-specific if kept for other providers |
| Multiple active providers simultaneously | Out of scope per PROJECT.md; selecting between providers at runtime adds complexity | One `MODEL` env var = one active provider; change env var to switch |
| Tool calling / function calling via litellm | Nanobot uses litellm's tool_calls support; FastCode does not use structured tool calling (agent uses internal Python tool dispatch, not LLM-native tool calling) | Do not add tool_calls support during this migration |
| litellm caching layer | litellm has built-in Redis/in-memory caching for identical prompts; FastCode already has its own `CacheManager` for BM25/vector results | Do not enable litellm's semantic cache — it would conflict with FastCode's existing cache strategy and introduce unexpected behavior |

---

## Feature Dependencies (Full Map)

```
[Must work — Table Stakes]
litellm.completion() sync
  └─ requires: model prefix "vertex_ai/" in MODEL env var
  └─ requires: VERTEXAI_PROJECT env var
  └─ requires: VERTEXAI_LOCATION env var
  └─ requires: ADC credentials (gcloud auth application-default login locally,
               service account / workload identity in GCP)
  └─ requires: litellm.drop_params = True (set at startup)

litellm.completion(stream=True)
  └─ requires: litellm.completion() sync (same code path)
  └─ requires: chunk iteration pattern preserved:
               for chunk in response:
                   chunk.choices[0].delta.content  ← same as current OpenAI pattern
               (Anthropic stream.text_stream must be REPLACED with this pattern)

Token counting compatibility
  └─ currently: tiktoken in fastcode/utils.py
  └─ problem: tiktoken has no tokenizer for VertexAI/Gemini model names
  └─ fix: replace count_tokens() with litellm.token_counter(model, messages)
           OR use cl100k_base as fallback (approximate but good enough)

[Differentiator — should enable]
litellm.suppress_debug_info = True  (no dependency, just startup config)
litellm.drop_params = True          (must be set before first completion call)

[Anti-features — must NOT build]
LiteLLM Proxy server
Custom wrapper class around litellm
Dual openai + litellm code paths
```

---

## MVP Recommendation

For this migration, the minimum viable feature set is:

1. **`litellm.completion()` with `vertex_ai/` prefix** — replaces all 4 provider-specific call paths
2. **`stream=True` support** — preserves `answer_generator.generate_stream()` without behavior change
3. **ADC auth via env vars** (`VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`) — no secrets in code
4. **`litellm.drop_params = True` at startup** — prevents parameter rejection crashes
5. **Token counting fix** — replace tiktoken in `utils.py` with a VertexAI-compatible counter

Defer:
- `litellm.acompletion()` async: Requires FastCode sync→async refactor — separate milestone
- Observability callbacks: Nice-to-have for production; not needed for functional migration
- Budget tracking: Operational concern, post-migration

---

## Complexity Assessment Per Call Site

| File | Current Pattern | litellm Replacement | Effort |
|------|----------------|---------------------|--------|
| `fastcode/answer_generator.py` | `OpenAI(...)` + `Anthropic(...)` init; two `_generate_*` methods + two `_generate_*_stream` methods | Single `litellm.completion()` call with `stream=True/False`; remove `_generate_openai`, `_generate_openai_stream`, `_generate_anthropic`, `_generate_anthropic_stream` | Medium — streaming filter logic in `_stream_with_summary_filter()` stays unchanged; only the generator source changes |
| `fastcode/query_processor.py` | `OpenAI(...)` + `Anthropic(...)` init; `_call_openai()` + `_call_anthropic()` methods | Single `litellm.completion()` call; remove both `_call_*` methods and `_initialize_llm_client()` | Low — no streaming, simple text response |
| `fastcode/iterative_agent.py` | Same init pattern as query_processor; uses `openai_chat_completion()` helper from `llm_utils.py` | `litellm.completion()` directly; remove `_initialize_client()` | Low-Medium — must read remaining call sites to confirm (file too large to read fully) |
| `fastcode/llm_utils.py` | `openai_chat_completion()` helper with `max_tokens`/`max_completion_tokens` fallback | Possibly delete entirely, or replace with thin litellm wrapper; litellm's `drop_params=True` handles the `max_completion_tokens` fallback case automatically | Low — likely can be deleted |
| `fastcode/utils.py` | `count_tokens()` uses `tiktoken.encoding_for_model()` | Replace with `litellm.token_counter(model, text)` or fallback to `cl100k_base` tokenizer | Low — isolated utility function |

---

## Sources

- Codebase analysis: `/Users/knakanishi/Repositories/FastCode/fastcode/answer_generator.py` (direct read)
- Codebase analysis: `/Users/knakanishi/Repositories/FastCode/fastcode/query_processor.py` (direct read)
- Codebase analysis: `/Users/knakanishi/Repositories/FastCode/fastcode/iterative_agent.py` (partial read, first 100 lines)
- Codebase analysis: `/Users/knakanishi/Repositories/FastCode/fastcode/llm_utils.py` (direct read)
- Reference implementation: `/Users/knakanishi/Repositories/FastCode/nanobot/nanobot/providers/litellm_provider.py` (direct read) — HIGH confidence for litellm API shape
- Project requirements: `/Users/knakanishi/Repositories/FastCode/.planning/PROJECT.md` (direct read)
- litellm API shape (sync completion, streaming, VertexAI prefix, ADC, drop_params): HIGH confidence — corroborated by Nanobot reference implementation using `litellm>=1.0.0`
- VertexAI env var names (`VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`): MEDIUM confidence — standard litellm VertexAI convention, unverified against current docs (WebFetch blocked during research)
- tiktoken incompatibility with Gemini model names: HIGH confidence — tiktoken only knows OpenAI model names; `cl100k_base` fallback is a well-known workaround
