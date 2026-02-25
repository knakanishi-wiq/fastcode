# Phase 4: Streaming Migration and Finalization - Research

**Researched:** 2026-02-25
**Domain:** litellm streaming, Python generator migration, YAML config cleanup
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Constructor cleanup**
- Delete `_initialize_client()`, `self.client`, `self.provider`, `self.api_key`, `self.anthropic_api_key`, `self.base_url` (the env-loaded one) entirely
- Keep `self.model = os.getenv("MODEL")` — still needed for token counting and llm_client calls
- Keep `load_dotenv()` — MODEL and VERTEXAI_* vars still come from .env, and ensures answer_generator works standalone in tests
- All credential handling is delegated to llm_client

**_stream_with_summary_filter approach**
- Replace the provider dispatch (openai vs anthropic) with a single `llm_client.completion_stream()` call
- Keep existing buffering and regex tag detection logic intact — it's correct, and the chunk format change doesn't require it
- litellm normalizes output to OpenAI-compatible format (`chunk.choices[0].delta.content`), so chunk extraction stays the same
- Do NOT simplify the buffer-holding logic — keep it as-is to minimize risk

**generate() non-streaming path**
- Delete `_generate_openai()` and `_generate_anthropic()` methods entirely (success criteria requires no such methods)
- Replace provider dispatch in `generate()` with a direct `llm_client.completion()` call
- Use the same defensive check pattern as Phase 3 migrations: check `response.choices`, then `response.choices[0].message.content`

**generate_stream() path**
- Delete `_generate_openai_stream()` and `_generate_anthropic_stream()` methods entirely
- Replace provider dispatch in `generate_stream()` with `llm_client.completion_stream()` (same as _stream_with_summary_filter)

**Config cleanup**
- Delete `generation.provider: "openai"` line from `config/config.yaml` entirely (no replacement, no comment)
- Update the NOTE comment in config.yaml from "model and base_url are read from environment variables (MODEL, BASE_URL)" to "model is read from MODEL env var"
- Remove `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `BASE_URL` from `.env.example` — keep only `MODEL` and `VERTEXAI_*` vars

### Claude's Discretion
- Exact litellm import style in answer_generator.py (import llm_client module vs specific functions)
- Whether to add a defensive None-guard for `delta.content` in the new stream extractor (litellm may emit finish-reason chunks with no content)
- Test structure and coverage approach

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STRM-01 | `answer_generator.py` non-streaming `generate()` uses litellm via `llm_client` | Verified: `llm_client.completion(model, messages, **kwargs)` returns `ModelResponse`; use `response.choices[0].message.content` — identical defensive pattern as Phase 3 iterative_agent.py |
| STRM-02 | `answer_generator.py` streaming `generate_stream()` uses litellm via `llm_client` | Verified: `llm_client.completion_stream(model, messages, **kwargs)` returns `CustomStreamWrapper`; iterate with `for chunk in stream: chunk.choices[0].delta.content or ""` |
| STRM-03 | `_stream_with_summary_filter()` works correctly with litellm chunk format | Verified: litellm normalizes all providers to OpenAI format; `chunk.choices[0].delta.content` is the extraction path; `delta.content` is `None` on finish-reason chunks — guard required |
| CONF-03 | `config.yaml` cleaned of provider-specific sections (no more `openai`/`anthropic` branches) | Confirmed: `config/config.yaml` line 145 has `provider: "openai"` to delete; line 143 has NOTE comment to update; `.env.example` has three vars to remove |
</phase_requirements>

---

## Summary

Phase 4 is the final migration step: `answer_generator.py` is the last file still using direct `openai` and `anthropic` clients plus the deleted `llm_utils` module. The migration pattern is fully established from Phase 3 (4 files already migrated) and this phase applies the same pattern to the two remaining code paths: non-streaming (`generate()`) and streaming (`generate_stream()` and `_stream_with_summary_filter()`).

The streaming path has one non-trivial consideration: litellm emits finish-reason chunks where `delta.content` is `None`. The existing `_generate_openai_stream()` already guards this with `if hasattr(delta, 'content') and delta.content:`. The new litellm-based extractor must carry the same guard — the idiomatic litellm pattern is `chunk.choices[0].delta.content or ""`. The `_stream_with_summary_filter()` function's buffering and regex logic needs no changes; only the stream source (the few lines that dispatch to `_generate_openai_stream()` or `_generate_anthropic_stream()`) is replaced.

The config cleanup is surgical: one YAML line deleted, one YAML comment updated, three `.env.example` lines deleted. No renames, no restructuring.

**Primary recommendation:** Apply the exact Phase 3 `llm_client.completion()` pattern to `generate()`, apply `llm_client.completion_stream()` to replace the two stream dispatch blocks, add the `delta.content or ""` None-guard in the new extractor, then clean config. Four atomic changes, each independently verifiable.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastcode.llm_client` | (project module, Phase 2) | Thin litellm wrapper — `completion()`, `completion_stream()` | Established in Phase 2; all Phase 3 files already use it |
| `litellm` | pinned in requirements.txt | Normalizes all LLM providers to OpenAI format; `CustomStreamWrapper` for streaming | Already installed, `drop_params=True` and `suppress_debug_info=True` set at import time |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `utils.count_tokens` | (project module) | Token counting, stays as-is | `answer_generator.py` keeps `count_tokens` from `utils.py` — NOT migrated to `llm_client.count_tokens` in this phase |
| `utils.truncate_to_tokens` | (project module) | Context truncation, stays as-is | Used in `_truncate_context()` — no change needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `from fastcode import llm_client` (module import) | `from fastcode.llm_client import completion, completion_stream` | Module import keeps the `llm_client.` namespace prefix consistent with Phase 3 files (query_processor.py, iterative_agent.py all use `from fastcode import llm_client`) |

---

## Architecture Patterns

### Recommended Project Structure

No structural changes. `answer_generator.py` stays in `fastcode/answer_generator.py`. This is a method-level migration only.

### Pattern 1: Non-Streaming LLM Call (Phase 3 established pattern)

**What:** Replace provider-dispatched `_generate_openai()` / `_generate_anthropic()` with a single `llm_client.completion()` call directly in `generate()`.

**When to use:** Everywhere `generate()` previously dispatched to provider-specific methods.

**Example (from iterative_agent.py — the canonical Phase 3 pattern):**
```python
# Source: /Users/knakanishi/Repositories/FastCode/fastcode/iterative_agent.py lines 2447-2461
response = llm_client.completion(
    model=llm_client.DEFAULT_MODEL,
    messages=[
        {"role": "system", "content": "..."},
        {"role": "user", "content": prompt},
    ],
    temperature=self.temperature,
    max_tokens=self.max_tokens,
)
if not response or not getattr(response, "choices", None):
    raise ValueError(f"Empty response from LLM: {response}")
content = response.choices[0].message.content
if not content:
    raise ValueError("LLM returned empty content in response")
return content
```

**Adaptation for answer_generator.py:** Use `self.model` instead of `llm_client.DEFAULT_MODEL` (CONTEXT.md: "Keep `self.model = os.getenv("MODEL")`"). Pass prompt as a single user message (no system message needed — prompt already contains the full system+user text from `_build_prompt()`).

```python
# Pattern for generate() — adapted from Phase 3
response = llm_client.completion(
    model=self.model,
    messages=[{"role": "user", "content": prompt}],
    temperature=self.temperature,
    max_tokens=self.max_tokens,
)
if not response or not getattr(response, "choices", None):
    raise ValueError(f"Empty response or no choices returned: {response}")
content = response.choices[0].message.content
if content is None:
    raise ValueError(f"LLM response has no content: {response}")
return content
```

### Pattern 2: Streaming LLM Call

**What:** Replace provider dispatch in `generate_stream()` and `_stream_with_summary_filter()` with `llm_client.completion_stream()`.

**When to use:** Both places that previously called `_generate_openai_stream()` or `_generate_anthropic_stream()`.

**Example (verified from litellm official docs):**
```python
# Source: https://docs.litellm.ai/docs/completion/stream
response = completion(model="gpt-3.5-turbo", messages=messages, stream=True)
for part in response:
    print(part.choices[0].delta.content or "")
```

**Adaptation for answer_generator.py:**
```python
# In generate_stream() normal (non-filter) path — replaces the openai/anthropic dispatch block
stream = llm_client.completion_stream(
    model=self.model,
    messages=[{"role": "user", "content": prompt}],
    temperature=self.temperature,
    max_tokens=self.max_tokens,
)
for chunk in stream:
    text = chunk.choices[0].delta.content or ""
    if text:
        full_response.append(text)
        yield text, None
```

**Adaptation for `_stream_with_summary_filter()`:**
```python
# Replace the provider dispatch block (lines 351-358 in current answer_generator.py)
stream_generator = llm_client.completion_stream(
    model=self.model,
    messages=[{"role": "user", "content": prompt}],
    temperature=self.temperature,
    max_tokens=self.max_tokens,
)

for chunk in stream_generator:
    chunk_text = chunk.choices[0].delta.content or ""
    if not chunk_text:
        continue  # skip finish-reason or empty chunks
    # ... rest of existing buffering logic unchanged, using chunk_text as `chunk`
```

### Pattern 3: Import Style

**What:** Import `llm_client` as a module, matching all Phase 3 files.

```python
# Matches query_processor.py and iterative_agent.py exactly
from fastcode import llm_client
```

**What to remove from imports:**
```python
# DELETE these lines:
from openai import OpenAI
from anthropic import Anthropic
from .llm_utils import openai_chat_completion
```

**What to keep:**
```python
# KEEP — count_tokens and truncate_to_tokens still come from utils.py in this phase
from .utils import count_tokens, truncate_to_tokens
```

### Anti-Patterns to Avoid

- **Passing `system=` as a kwarg to litellm:** silently dropped for some providers. Phase 3 decision: pass system message in the `messages` list. However, `answer_generator.py`'s `_build_prompt()` already concatenates system+user into a single string and passes it as `{"role": "user", "content": prompt}` — no system message kwarg issue here.
- **Yielding `chunk.choices[0].delta.content` directly without None-guard:** litellm emits finish-reason chunks with `delta.content = None`. The existing `_generate_openai_stream()` guards this. The new code must use `chunk.choices[0].delta.content or ""` and skip empty strings.
- **Replacing `_stream_with_summary_filter()`'s buffering logic:** the CONTEXT.md decision is "swap the stream source, touch nothing else." The variable named `chunk` in the existing loop must match the new extractor output (a plain string).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Streaming chunk extraction | Custom delta parser | `chunk.choices[0].delta.content or ""` | litellm normalizes all providers to OpenAI chunk format — verified by docs |
| Provider detection at runtime | Re-add `if self.provider == "openai"` branching | `llm_client.completion_stream()` | litellm routes based on model string prefix (`vertex_ai/`, `openai/`, etc.) — no provider flag needed |
| Config value cleanup | Leave `generation.provider` with a deprecation comment | Delete the line entirely | CONTEXT.md: "no replacement, no comment" |

**Key insight:** litellm's normalization means zero provider-specific chunk handling. The only stream-level concern is the `None` guard for finish-reason chunks, which is a one-liner.

---

## Common Pitfalls

### Pitfall 1: `delta.content` is None on Finish-Reason Chunks

**What goes wrong:** The final chunk(s) litellm yields have `finish_reason="stop"` and `delta.content = None`. Code that does `yield chunk.choices[0].delta.content` without guarding will propagate `None` into the buffer, causing `buffer + None` TypeErrors.

**Why it happens:** OpenAI streaming protocol sends a final `[DONE]` signal as a chunk with no content. litellm normalizes this to a chunk object with `delta.content = None` (documented in the litellm v1.0.0 migration guide).

**How to avoid:** Always use `chunk.choices[0].delta.content or ""` (returns `""` if `None`). Then skip empty strings before passing to the buffer: `if not chunk_text: continue`.

**Warning signs:** `TypeError: can only concatenate str (not "NoneType") to str` inside `_stream_with_summary_filter()`.

### Pitfall 2: `_stream_with_summary_filter()` Variable Rename Mismatch

**What goes wrong:** The existing loop body uses `chunk` as the variable name (a plain string from `_generate_openai_stream()`). The new code must yield plain strings into the same variable. If the extractor yields chunk objects instead of `str`, all the `buffer + chunk` string operations fail.

**Why it happens:** The old stream generators (`_generate_openai_stream`, `_generate_anthropic_stream`) already extracted `.delta.content` and `yield`ed plain strings. The new code must extract content from the litellm chunk object BEFORE assigning to `chunk`.

**How to avoid:** In the new stream_generator iteration:
```python
for raw_chunk in stream_generator:
    chunk = raw_chunk.choices[0].delta.content or ""
    if not chunk:
        continue
    original_chunk = chunk
    # ... rest of existing buffering logic unchanged
```

**Warning signs:** `AttributeError: 'str' object has no attribute 'choices'` or `TypeError` in buffer concatenation.

### Pitfall 3: `self.model` vs `llm_client.DEFAULT_MODEL`

**What goes wrong:** Using `llm_client.DEFAULT_MODEL` (hardcoded `vertex_ai/gemini-2.0-flash-001`) instead of `self.model` (from `os.getenv("MODEL")`).

**Why it happens:** Phase 3 files (iterative_agent.py) use `llm_client.DEFAULT_MODEL`. But `answer_generator.py`'s CONTEXT.md decision explicitly keeps `self.model = os.getenv("MODEL")` for both token counting and LLM calls.

**How to avoid:** Always use `self.model` in the `llm_client.completion()` and `llm_client.completion_stream()` calls inside `answer_generator.py`.

**Warning signs:** Model routing goes to wrong provider when `MODEL` env var is set to something other than the default.

### Pitfall 4: `count_tokens` Signature Confusion

**What goes wrong:** Accidentally migrating `count_tokens` to `llm_client.count_tokens(model, text)` which has reversed argument order vs `utils.count_tokens(text, model)`. The existing calls are `count_tokens(prompt, self.model)` — `(text, model)` order from `utils.py`.

**Why it happens:** `llm_client.count_tokens` has the reversed signature `(model, text)` (documented in llm_client.py). Phase 4 scope does NOT include migrating `count_tokens`.

**How to avoid:** Keep `from .utils import count_tokens, truncate_to_tokens`. Do not add `llm_client.count_tokens` to this file. The existing call sites `count_tokens(prompt, self.model)` stay exactly as-is.

**Warning signs:** Token counts silently use the wrong argument as the model string (no error, just wrong counts) OR `EnvironmentError` from `llm_client` being imported at module level when `VERTEXAI_PROJECT` is unset.

### Pitfall 5: Removing `os` Import When It's Still Needed

**What goes wrong:** Deleting `import os` along with the client initialization code, but `os.getenv("MODEL")` is still in `__init__`.

**Why it happens:** Phase 3 files had mixed results — some deleted `os` (query_processor, repo_selector), some kept it (repo_overview, iterative_agent). The trigger is whether `os` is used outside the dead constructor code.

**How to avoid:** After deleting the constructor cleanup lines, verify `os.getenv("MODEL")` remains in `__init__`. Since it does, `import os` stays.

**Warning signs:** `NameError: name 'os' is not defined` at class instantiation.

---

## Code Examples

Verified patterns from official sources and project codebase:

### Non-Streaming Completion (litellm official docs + project pattern)
```python
# Source: https://docs.litellm.ai/docs/completion/stream + iterative_agent.py
response = llm_client.completion(
    model=self.model,
    messages=[{"role": "user", "content": prompt}],
    temperature=self.temperature,
    max_tokens=self.max_tokens,
)
if not response or not getattr(response, "choices", None):
    raise ValueError(f"Empty response or no choices returned: {response}")
content = response.choices[0].message.content
if content is None:
    raise ValueError(f"LLM response has no content: {response}")
return content
```

### Streaming with None-Guard (litellm migration guide)
```python
# Source: https://docs.litellm.ai/docs/migration
# "OpenAI Chunks will now return None for empty stream chunks"
stream = llm_client.completion_stream(
    model=self.model,
    messages=[{"role": "user", "content": prompt}],
    temperature=self.temperature,
    max_tokens=self.max_tokens,
)
for raw_chunk in stream:
    chunk_text = raw_chunk.choices[0].delta.content or ""
    if not chunk_text:
        continue
    yield chunk_text
```

### Summary Filter Stream Source Replacement

The summary filter function currently has this dispatch (lines 351–358):
```python
# CURRENT (delete this block):
if self.provider == "openai":
    stream_generator = self._generate_openai_stream(prompt)
elif self.provider == "anthropic":
    stream_generator = self._generate_anthropic_stream(prompt)
else:
    yield "Error: LLM provider not configured", "Error: LLM provider not configured"
    return
```

Replace with:
```python
# NEW (single llm_client call):
stream_generator = llm_client.completion_stream(
    model=self.model,
    messages=[{"role": "user", "content": prompt}],
    temperature=self.temperature,
    max_tokens=self.max_tokens,
)
```

And update the loop that iterates `stream_generator` to extract content before passing to the buffer logic:
```python
# CURRENT loop start (line 360):
for chunk in stream_generator:
    original_chunk = chunk
    ...

# NEW loop start (content extracted from litellm chunk):
for raw_chunk in stream_generator:
    chunk = raw_chunk.choices[0].delta.content or ""
    if not chunk:
        continue
    original_chunk = chunk
    # ... rest of buffering logic UNCHANGED
```

### Config YAML Cleanup

```yaml
# config/config.yaml — BEFORE (lines 142-146):
# NOTE: model and base_url are read from environment variables (MODEL, BASE_URL)
generation:
  provider: "openai"  # openai, anthropic, or local
  temperature: 0.4

# config/config.yaml — AFTER:
# NOTE: model is read from MODEL env var
generation:
  temperature: 0.4
```

### .env.example Cleanup

```bash
# .env.example — BEFORE:
OPENAI_API_KEY=your_openai_api_key_here
MODEL=your_model
BASE_URL=your_base_url

# .env.example — AFTER (keep only MODEL):
MODEL=your_model
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct `OpenAI(api_key=..., base_url=...)` client | `llm_client.completion(model, messages)` | Phase 2 infrastructure, Phase 3 migration | No provider-specific client initialization needed |
| `self.provider` dispatch (`if provider == "openai"`) | Model string prefix routing in litellm (`vertex_ai/`, `openai/`, etc.) | Phase 3 complete | `provider` field no longer needs to exist in config or constructor |
| `openai_chat_completion()` wrapper from `llm_utils.py` | `llm_client.completion()` direct call | Phase 2 (llm_utils.py deleted) | `from .llm_utils import openai_chat_completion` must be removed |
| Anthropic `messages.stream()` context manager | litellm `completion(..., stream=True)` yielding OpenAI-format chunks | Phase 4 | Uniform chunk format: `chunk.choices[0].delta.content` |

**Deprecated/outdated:**
- `llm_utils.py`: Deleted in Phase 2. `answer_generator.py` still imports `openai_chat_completion` from it — this import causes an `ImportError` at runtime and must be removed in Phase 4.
- `self.provider`, `self.client`, `self.api_key`, `self.anthropic_api_key`, `self.base_url` (env-loaded): All dead weight after this migration.
- `_generate_openai()`, `_generate_openai_stream()`, `_generate_anthropic()`, `_generate_anthropic_stream()`: All four deleted.

---

## Open Questions

1. **Should `generate()` and `generate_stream()` pass prompt as a single user message or split into system+user?**
   - What we know: `_build_prompt()` concatenates system and user content into a single string (line 625: `full_prompt = f"{system_prompt}\n\n{user_prompt}"`). The existing code passes this as `[{"role": "user", "content": prompt}]` in `_generate_openai()`.
   - What's clear: No change needed — keep the single `user` message as-is. The Phase 3 decision "system message in messages list" (for iterative_agent) is not applicable here because `_build_prompt()` already bakes the system prompt into the user message string.
   - Recommendation: Pass as `[{"role": "user", "content": prompt}]` — matches current behavior exactly.

2. **Does `generate_stream()` need the `self.provider` check removed from the `filter_summary` branch too?**
   - What we know: When `filter_summary=True`, `generate_stream()` calls `_stream_with_summary_filter(prompt)` which internally dispatches to the stream generator. The `if self.provider == "openai"` dispatch lives inside `_stream_with_summary_filter()`, not in `generate_stream()` directly.
   - What's clear: The `else` branch in `generate_stream()` (lines 284–295) has the dispatch for the non-filter path. The filter path doesn't need its own dispatch fix — fixing `_stream_with_summary_filter()` covers it.
   - Recommendation: Fix the `else` branch dispatch in `generate_stream()` AND fix `_stream_with_summary_filter()` — both changes required for full coverage.

---

## Sources

### Primary (HIGH confidence)
- `/berriai/litellm` via Context7 — streaming chunk format, `CustomStreamWrapper`, `delta.content or ""` pattern
- `/websites/litellm_ai` via Context7 — migration guide (None on empty chunks), streaming examples
- `/Users/knakanishi/Repositories/FastCode/fastcode/answer_generator.py` — current implementation (read directly)
- `/Users/knakanishi/Repositories/FastCode/fastcode/llm_client.py` — `completion_stream()` signature confirmed
- `/Users/knakanishi/Repositories/FastCode/fastcode/iterative_agent.py` lines 2447-2461 — canonical Phase 3 `llm_client.completion()` pattern
- `/Users/knakanishi/Repositories/FastCode/fastcode/query_processor.py` — `from fastcode import llm_client` import style confirmed
- `/Users/knakanishi/Repositories/FastCode/config/config.yaml` — `provider: "openai"` at line 145, NOTE comment at line 143, confirmed targets
- `/Users/knakanishi/Repositories/FastCode/.env.example` — `OPENAI_API_KEY`, `MODEL`, `BASE_URL` present, confirmed targets

### Secondary (MEDIUM confidence)
- litellm official docs: https://docs.litellm.ai/docs/completion/stream — streaming pattern verified
- litellm migration guide: https://docs.litellm.ai/docs/migration — None on empty chunk behavior confirmed

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — llm_client module confirmed in codebase; litellm streaming API verified via Context7
- Architecture: HIGH — all four target methods identified in source; exact replacement code derived from established Phase 3 patterns
- Pitfalls: HIGH — `delta.content = None` confirmed via litellm migration docs; variable name collision confirmed by reading actual code; `count_tokens` signature confirmed by reading both utils.py and llm_client.py
- Config targets: HIGH — exact line numbers confirmed by reading config.yaml and .env.example

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (litellm streaming API is stable; project code confirmed current)
