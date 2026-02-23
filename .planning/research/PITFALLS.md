# Domain Pitfalls: litellm + VertexAI Migration

**Domain:** LLM provider abstraction migration (direct openai/anthropic → litellm + VertexAI)
**Project:** FastCode — litellm provider migration
**Researched:** 2026-02-24
**Overall confidence:** HIGH (based on direct codebase analysis + litellm/VertexAI documented behavior)

---

## Critical Pitfalls

Mistakes that require rewrites, cause silent regressions, or break the service at runtime.

---

### Pitfall 1: tiktoken Token Counting Silently Wrong for VertexAI Models

**What goes wrong:**
`fastcode/utils.py` uses `tiktoken.encoding_for_model(model)` for all token counting. tiktoken only knows OpenAI model families. When `model` becomes `vertex_ai/gemini-1.5-pro` or `vertex_ai/claude-3-5-sonnet@20241022`, `tiktoken.encoding_for_model()` raises `KeyError` and silently falls back to `cl100k_base` (GPT-4 encoding). Gemini and Claude have different tokenizers; this under-counts or over-counts tokens by 15–40% depending on content.

**Where it happens in FastCode:**
- `fastcode/utils.py` — `count_tokens()` and `truncate_to_tokens()` (both called with `self.model`)
- `fastcode/answer_generator.py` — `generate()` and `generate_stream()` call `count_tokens(prompt, self.model)` to decide whether to truncate context
- The token budget calculation: `available_input_tokens = max_context_tokens - max_tokens - reserve_tokens` is the only guard before sending a request. Wrong token counts mean this guard either truncates too early (wastes context) or too late (overflows the model's context window, causing a 400 error at API call time).

**Consequences:**
- 400 errors mid-request if context overflows (happens during streaming, not caught cleanly)
- Context truncated unnecessarily early → degraded answer quality
- The fallback silently accepts wrong counts — no warning is logged

**Prevention:**
Replace the tiktoken-based `count_tokens()` with `litellm.token_counter(model=model, text=text)` after migration. litellm's token counter handles VertexAI model names and falls back to a reasonable approximation rather than using OpenAI-specific tokenizer encoding.

**Detection (warning signs):**
- `KeyError` in logs from tiktoken during initial testing with a VertexAI model name
- Prompt truncation logs firing earlier than expected (check `"Prompt exceeds limit"` log line)
- Answer quality drops on long-context queries after migration

**Phase:** Address in the token counting migration step, before any integration testing.

---

### Pitfall 2: VertexAI Model Name Format Is Not Obvious and Varies by Model Family

**What goes wrong:**
litellm requires the `vertex_ai/` prefix for VertexAI routing. The model name after the prefix must match VertexAI's exact model ID format, which differs between Gemini models and Anthropic-on-Vertex models:

- Gemini: `vertex_ai/gemini-1.5-pro-002` (no `@` version suffix in most cases)
- Anthropic-on-Vertex: `vertex_ai/claude-3-5-sonnet@20241022` (requires the `@VERSION` suffix — without it, VertexAI rejects the request)
- Using the standard Anthropic format `anthropic/claude-3-5-sonnet-20241022` (hyphen, not `@`) will route to Anthropic's API, not VertexAI, silently ignoring the intended provider

FastCode currently stores the model name in a single `MODEL` env var. After migration, the `vertex_ai/` prefix must be included in the model name, not added by application logic separately.

**Where it happens in FastCode:**
- `MODEL` env var consumed identically by `answer_generator.py`, `query_processor.py`, `iterative_agent.py`, and `repo_overview.py`
- `openai_chat_completion()` in `llm_utils.py` calls `client.chat.completions.create(model=self.model, ...)` — the model name is passed straight through

**Consequences:**
- Requests silently routed to Anthropic Direct instead of VertexAI (charges wrong account, bypasses GCP auth)
- 404 or 400 from VertexAI if model version suffix is wrong (e.g., missing `@20241022`)
- Different models within VertexAI behave differently under the same config

**Prevention:**
Document the exact env var format in `.env.example`. Test with a simple `litellm.completion(model="vertex_ai/...", messages=[...])` smoke test before wiring it into FastCode. Use `VERTEX_AI_MODEL=vertex_ai/gemini-1.5-pro` for Gemini; `vertex_ai/claude-3-5-sonnet@20241022` for Claude-on-Vertex.

**Detection (warning signs):**
- Requests succeed but bill to Anthropic, not GCP
- API error mentioning "model not found" or version mismatch from VertexAI endpoint
- litellm logs show routing to `anthropic` instead of `vertex_ai`

**Phase:** Address during VertexAI config setup, before code migration begins.

---

### Pitfall 3: Streaming Response Object Structure Is Different — Will Break `generate_stream()`

**What goes wrong:**
The current streaming paths use provider-specific iteration:

- OpenAI path: iterates `for chunk in response`, reads `chunk.choices[0].delta.content`
- Anthropic path: uses `with self.client.messages.stream(...) as stream: for text in stream.text_stream`

litellm's sync streaming returns a generator of `ModelResponse` objects with `choices[0].delta.content` (OpenAI-compatible format for all providers). The Anthropic-style `messages.stream()` context manager does not exist in litellm. Calling `litellm.completion(..., stream=True)` and treating it like an Anthropic stream context manager will raise `AttributeError`.

**Where it happens in FastCode:**
- `fastcode/answer_generator.py` — `_generate_openai_stream()` and `_generate_anthropic_stream()` are both called from `_stream_with_summary_filter()` depending on `self.provider`
- `_stream_with_summary_filter()` contains the summary-tag filtering logic (120+ lines); it yields `(original_chunk, filtered_chunk)` tuples
- `generate_stream()` calls `_stream_with_summary_filter()` and drives the SSE response in `web_app.py`

**Consequences:**
- `_generate_anthropic_stream()` crashes immediately if rewritten to call `litellm.completion(stream=True)` without updating the iteration pattern
- Summary-tag filtering (`<SUMMARY>` detection logic) receives chunks of different sizes than before — litellm chunk size varies by provider, so the tag-boundary detection buffer logic may not work correctly
- The `(original_chunk, filtered_chunk)` generator contract must be preserved exactly for `generate_stream()` callers

**Prevention:**
After replacing both `_generate_openai_stream()` and `_generate_anthropic_stream()` with a single litellm call, verify that the iteration pattern is:
```python
for chunk in litellm.completion(..., stream=True):
    delta = chunk.choices[0].delta
    if delta and delta.content:
        yield delta.content
```
Do not try to use `chunk.delta.text` (Anthropic-style) — litellm normalizes to `choices[0].delta.content` for all providers.

**Detection (warning signs):**
- `AttributeError: 'ModelResponse' has no attribute 'delta'` or similar in streaming path
- Streaming tests return empty output or hang on first SSE chunk
- Summary tags pass through unfiltered (chunk boundary shifts make the buffer logic miss the tag)

**Phase:** Highest-risk code path. Test streaming end-to-end (both SSE and non-streaming) before marking migration complete.

---

### Pitfall 4: ADC Authentication Fails Silently in Docker

**What goes wrong:**
Application Default Credentials (ADC) work via `gcloud auth application-default login` on a developer workstation, which writes credentials to `~/.config/gcloud/application_default_credentials.json`. In Docker, this file must be explicitly mounted into the container. litellm's VertexAI handler calls `google.auth.default()` at request time — if credentials are not present, it raises `google.auth.exceptions.DefaultCredentialsError` at the first LLM call, not at startup. The FastCode initialization pattern (deferred errors until first API call) means this fails silently during startup checks.

**Where it happens in FastCode:**
- `fastcode/answer_generator.py` `_initialize_client()` — logs a warning for missing `OPENAI_API_KEY` but does not raise; initialization succeeds with `client = None` or a partial client
- After migration, `litellm.completion()` is called without any client object (litellm manages auth internally via env vars and ADC), so the first call to any endpoint is when auth is validated

**Consequences:**
- Container starts successfully with no errors logged
- First query returns `"Error generating answer: google.auth.exceptions.DefaultCredentialsError"` to the user
- Debugging is difficult because the error appears at query time, not startup

**Prevention:**
1. Mount ADC credentials in `docker-compose.yml`:
   ```yaml
   volumes:
     - ~/.config/gcloud:/root/.config/gcloud:ro
   ```
2. Set `GOOGLE_APPLICATION_CREDENTIALS` env var pointing to the mounted file, OR use Workload Identity in GCP
3. Add a startup health check that makes a trivial litellm call (single token generation) to validate auth before the service is marked healthy
4. Set `VERTEXAI_PROJECT` and `VERTEXAI_LOCATION` env vars (required by litellm's VertexAI handler)

**Detection (warning signs):**
- Service starts cleanly but first query fails with credentials error
- `docker logs fastcode` shows no errors at startup
- ADC credentials file not present inside the container (`docker exec fastcode ls ~/.config/gcloud/`)

**Phase:** Must be addressed in the Docker/config setup phase, verified before deploying to any shared environment.

---

### Pitfall 5: `system` Parameter Handled Differently Across Providers via litellm

**What goes wrong:**
`fastcode/iterative_agent.py`'s `_call_llm()` passes a `system` message as the first message in the `messages` list using the OpenAI format:
```python
messages=[
    {"role": "system", "content": "You are a precise code analysis agent..."},
    {"role": "user", "content": prompt}
]
```
litellm normalizes this for most providers. However, some VertexAI models (notably Gemini) do not support `role: system` in the messages array; litellm converts system messages to a `system_instruction` parameter in the VertexAI API call, but this behavior changed across litellm versions. Gemini also returns an error if the messages array starts with a system message and the model does not support the `system_instruction` parameter.

**Where it happens in FastCode:**
- `fastcode/iterative_agent.py` `_call_llm()` — uses explicit `{"role": "system", ...}` message
- `fastcode/answer_generator.py` `_generate_openai()` and `_generate_openai_stream()` — pass a single `user` message (no system message), so this is safer

**Consequences:**
- 400 error from VertexAI Gemini models: "Invalid role 'system' in messages"
- If litellm does convert automatically, the system prompt behavior may change subtly (system instructions have different weight in Gemini vs OpenAI)

**Prevention:**
After migration, test the iterative agent specifically with the VertexAI model. If using Gemini, verify litellm version behavior on system message conversion. If using Claude-on-Vertex, the system message format is compatible.

**Detection (warning signs):**
- Iterative agent queries fail with 400 errors, while non-agent queries work fine
- Error message mentions "invalid role" or "system message not supported"
- Issue is Gemini-specific; Claude-on-Vertex handles system messages correctly

**Phase:** Test in iterative agent integration tests specifically.

---

## Moderate Pitfalls

---

### Pitfall 6: `llm_utils.openai_chat_completion()` `max_tokens` Fallback Is Unnecessary but Must Be Removed Correctly

**What goes wrong:**
`fastcode/llm_utils.py` implements a `BadRequestError` retry: if `max_tokens` is rejected, it retries with `max_completion_tokens`. This was written for OpenAI model differences (o1/o3 models use `max_completion_tokens`). After migration to litellm, this wrapper is no longer needed because litellm's `drop_params=True` (already used in Nanobot's provider) silently handles unsupported parameters. However, if `openai_chat_completion()` is kept and called with a litellm call, it will catch `litellm.exceptions.BadRequestError` (not `openai.BadRequestError`) — the import at the top of `llm_utils.py` is `from openai import BadRequestError`, which will not catch litellm-wrapped errors.

**Where it happens in FastCode:**
- `fastcode/llm_utils.py` — `openai_chat_completion()` wrapper
- Called from `answer_generator.py`, `query_processor.py`, `iterative_agent.py`

**Prevention:**
During migration, replace all calls to `openai_chat_completion()` with `litellm.completion()` directly. Do not attempt to keep the wrapper by changing the exception type — it adds complexity for no benefit since litellm handles parameter normalization.

**Detection (warning signs):**
- After migration, 400 errors that should be caught are surfacing as unhandled exceptions
- `openai.BadRequestError` never raised but errors still occur

**Phase:** Clean up during litellm replacement phase.

---

### Pitfall 7: Duplicate Client Initialization Across Four Files Creates Four Separate Auth Contexts

**What goes wrong:**
Each of the four LLM-calling files (`answer_generator.py`, `query_processor.py`, `iterative_agent.py`, and `repo_overview.py`) independently reads `os.getenv("OPENAI_API_KEY")`, `os.getenv("MODEL")`, etc. and creates its own client. After migration to litellm, the client is replaced by `litellm.completion()` calls which read credentials from environment variables globally. This is actually simpler. The pitfall is that each file currently also reads `GOOGLE_CLOUD_PROJECT`, `VERTEXAI_LOCATION`, and similar env vars at a different time; if any env var is missing at module init (e.g., it's set after `load_dotenv()` runs), only one of the four files might notice.

**Where it happens in FastCode:**
- `fastcode/answer_generator.py`, `fastcode/query_processor.py`, `fastcode/iterative_agent.py`, `fastcode/repo_overview.py` — all call `load_dotenv()` and `os.getenv()` in `__init__`

**Prevention:**
After migration, litellm reads env vars at call time (not at import time), so the distributed `load_dotenv()` pattern is harmless. However, document the required env vars (`VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`, `MODEL`) in one place (`.env.example`) and verify they are all present before each component initializes.

**Detection (warning signs):**
- One call site works (VertexAI auth succeeds) but another fails (credentials not found)
- `load_dotenv()` order dependency issues on container startup

**Phase:** Verify during integration testing across all four call sites.

---

### Pitfall 8: litellm Sync vs Async API — FastCode Is Synchronous, Nanobot Is Async

**What goes wrong:**
FastCode uses synchronous LLM calls throughout (`response = openai_chat_completion(...)`). Nanobot uses `await acompletion(...)` (async). litellm provides both `litellm.completion()` (sync) and `litellm.acompletion()` (async). FastCode's FastAPI endpoints use `async def` route handlers but call synchronous generator functions that yield streaming chunks. Mixing sync litellm calls inside async FastAPI route handlers works but blocks the event loop.

The specific risk: if litellm's sync `completion()` is called from within an `async def` handler, it blocks the event loop during the network I/O. For short queries this is acceptable; for long-context VertexAI calls (200k token context window) this can block the FastAPI event loop for 10–60 seconds.

**Where it happens in FastCode:**
- `web_app.py` and `api.py` both define `async def stream_query(...)` which calls `fastcode.generate_stream(...)` — a synchronous generator run inside `StreamingResponse`
- FastAPI's `StreamingResponse` with a sync generator runs it in a thread pool by default, so this is actually safe in practice

**Prevention:**
Keep sync litellm calls (`litellm.completion()`) for FastCode, consistent with the existing synchronous pattern. Do not mix `acompletion` into FastCode's synchronous pipeline. The StreamingResponse thread pool isolation means this is safe.

**Detection (warning signs):**
- Event loop blocking: other API endpoints become unresponsive during active streaming queries
- `RuntimeError: Event loop is closed` or `RuntimeError: This event loop is already running`

**Phase:** Low risk given existing sync pattern. Note in migration guide to not switch to `acompletion`.

---

### Pitfall 9: `temperature` Parameter Rejected by Certain VertexAI Models

**What goes wrong:**
Some models available on VertexAI do not accept a `temperature` parameter (notably the reasoning/thinking variants like `gemini-2.0-flash-thinking`). FastCode passes `temperature` in every LLM call. Without `litellm.drop_params = True`, these calls return a 400 error. Nanobot's `LiteLLMProvider` already sets `litellm.drop_params = True` globally, but FastCode's migration will use litellm without that global setting unless explicitly configured.

**Where it happens in FastCode:**
- All four LLM call sites pass `temperature=self.temperature` (values: 0.4 in `answer_generator.py`, 0.3 in `query_processor.py`, 0.2 in `iterative_agent.py`)
- `openai_chat_completion()` wrapper passes `temperature` as a kwarg directly to the API

**Prevention:**
At the point where litellm is initialized in FastCode, add:
```python
import litellm
litellm.drop_params = True
```
This should be set once at application startup (e.g., in `fastcode/main.py` or in a new `fastcode/llm_client.py` module), not per-call.

**Detection (warning signs):**
- 400 error "temperature is not supported for this model"
- Only affects reasoning-variant models; standard Gemini and Claude models accept temperature

**Phase:** Set `litellm.drop_params = True` in the initialization step.

---

### Pitfall 10: VertexAI Requires `VERTEXAI_PROJECT` and `VERTEXAI_LOCATION` — Missing Env Vars Produce Cryptic Errors

**What goes wrong:**
litellm's VertexAI handler requires `VERTEXAI_PROJECT` (GCP project ID) and `VERTEXAI_LOCATION` (e.g., `us-central1`) to be set as environment variables. If either is missing, the error message from the VertexAI API is typically an auth/permissions error (`401: Request had invalid authentication credentials`) rather than a config error, because the API call goes to a generic endpoint that rejects it at auth. This is misleading: it looks like an auth problem when it is actually a config problem.

**Where it happens in FastCode:**
- FastCode currently reads `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `MODEL`, `BASE_URL`
- After migration, new env vars `VERTEXAI_PROJECT` and `VERTEXAI_LOCATION` must be added
- `.env.example` does not currently include these

**Prevention:**
Update `.env.example` with:
```
VERTEXAI_PROJECT=your-gcp-project-id
VERTEXAI_LOCATION=us-central1
MODEL=vertex_ai/gemini-1.5-pro
```
Add a startup validation that checks for these vars and raises a clear `ConfigurationError` before the first LLM call.

**Detection (warning signs):**
- 401 error on first VertexAI call when ADC credentials appear correct
- `google.api_core.exceptions.PermissionDenied` with no obvious cause
- Works with `gcloud` CLI but fails in Python

**Phase:** Config setup phase. Block proceeding to code migration until smoke test passes with VertexAI.

---

## Minor Pitfalls

---

### Pitfall 11: litellm Logging Is Verbose by Default — Logs API Keys in Debug Mode

**What goes wrong:**
litellm logs request/response details at DEBUG level, including full messages and (in some versions) authorization headers. FastCode already has a known issue with LLM responses being printed to stdout (`query_processor.py` line 536). Adding litellm without suppressing its debug output will add more noise and potentially leak credentials in container logs.

**Prevention:**
Set `litellm.suppress_debug_info = True` alongside `litellm.drop_params = True` at startup. This is already done in Nanobot's `LiteLLMProvider.__init__()` — copy the same pattern.

**Phase:** Initialization step.

---

### Pitfall 12: Response Object Access Pattern Changes — `response.choices[0].message.content` Must Be Verified

**What goes wrong:**
FastCode has defensive attribute access guards like:
```python
if not response or not getattr(response, "choices", None):
    raise ValueError(...)
first_choice = response.choices[0]
message = getattr(first_choice, "message", None)
content = getattr(message, "content", None) if message else None
```
litellm returns a `ModelResponse` object with the same OpenAI-compatible structure, so these guards should work. However, for VertexAI streaming chunks, `choices[0].delta.content` can be `None` on the final chunk (finish chunk) — this is the same as OpenAI behavior and FastCode's existing `if delta.content:` guard handles it. The risk is minimal but worth verifying.

**Prevention:**
Keep the existing defensive access patterns. They are compatible with litellm's `ModelResponse`.

**Phase:** Verify during integration testing.

---

### Pitfall 13: Multi-Turn Dialogue Passes `role: assistant` Messages — Verify VertexAI Compatibility

**What goes wrong:**
FastCode's multi-turn dialogue builds message history arrays with `role: user` and `role: assistant` alternating. VertexAI Gemini requires strict user/model alternation (using `role: model`, not `role: assistant`). litellm normalizes `assistant` → `model` for Gemini automatically, but this normalization must be verified, as it has had regressions in past litellm releases.

**Where it happens in FastCode:**
- `fastcode/answer_generator.py` `_build_prompt()` builds dialogue history as `role: user` / `role: assistant` pairs
- `fastcode/query_processor.py` similarly uses dialogue history

**Prevention:**
Test a multi-turn dialogue sequence specifically against VertexAI after migration. Use `litellm.utils.validate_messages()` if available to check message format.

**Phase:** Integration testing phase.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| litellm dependency install | `google-cloud-aiplatform` transitive dependency conflicts with existing packages | Pin litellm version; test in fresh venv before adding to requirements.txt |
| VertexAI config setup | Missing `VERTEXAI_PROJECT` / `VERTEXAI_LOCATION` causes misleading 401 errors | Smoke test before code migration (Pitfall 10) |
| Token counting migration | tiktoken fallback silently wrong for VertexAI models | Replace with `litellm.token_counter()` immediately (Pitfall 1) |
| Replacing direct clients | `llm_utils.openai_chat_completion()` wrapper catches wrong exception type | Delete wrapper, use `litellm.completion()` directly (Pitfall 6) |
| Streaming migration | Anthropic stream context manager pattern incompatible with litellm | Rewrite both stream generators to use litellm chunk iteration (Pitfall 3) |
| Docker deployment | ADC credentials not mounted, silent failure at query time | Mount `~/.config/gcloud` in docker-compose.yml (Pitfall 4) |
| First integration test | `temperature` rejected by reasoning models | Set `litellm.drop_params = True` globally at startup (Pitfall 9) |
| System message handling | Gemini rejects `role: system` in messages array | Test iterative agent separately from answer generator (Pitfall 5) |

---

## Sources

- Direct codebase analysis: `fastcode/answer_generator.py`, `fastcode/llm_utils.py`, `fastcode/query_processor.py`, `fastcode/iterative_agent.py`, `fastcode/utils.py` (2026-02-24)
- Reference implementation: `nanobot/nanobot/providers/litellm_provider.py` — existing litellm usage patterns in this codebase (HIGH confidence)
- litellm VertexAI documentation: https://docs.litellm.ai/docs/providers/vertex (MEDIUM confidence — architecture and env var names; verify model name formats at migration time)
- litellm token counting: `litellm.token_counter()` documented at https://docs.litellm.ai/docs/completion/token_usage (MEDIUM confidence)
- ADC in Docker patterns: standard GCP documentation pattern; `GOOGLE_APPLICATION_CREDENTIALS` env var and volume mount are well-established (HIGH confidence)
- Gemini system message handling in litellm: reported in multiple litellm GitHub issues; litellm performs automatic conversion but version-dependent (MEDIUM confidence — verify against installed litellm version)
- `litellm.drop_params` setting: documented in litellm core docs, demonstrated in `nanobot/nanobot/providers/litellm_provider.py` line 39 (HIGH confidence)
- `litellm.suppress_debug_info`: demonstrated in `nanobot/nanobot/providers/litellm_provider.py` line 37 (HIGH confidence)

---

*Research date: 2026-02-24*
