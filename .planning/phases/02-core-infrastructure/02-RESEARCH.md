# Phase 2: Core Infrastructure - Research

**Researched:** 2026-02-24
**Domain:** litellm Python SDK — module-level configuration, completion API, token counting
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Module interface
- `completion(model, messages, **kwargs)` — mirrors litellm signature directly; callers pass model string explicitly
- `completion_stream(model, messages, **kwargs)` — returns litellm streaming iterator directly (ModelResponseStream); callers iterate chunks themselves, no wrapping
- `count_tokens(model, text)` — exported from llm_client alongside completion functions; matches llm_utils.py signature for easy migration

#### Configuration init
- litellm global settings (`drop_params=True`, `suppress_debug_info=True`) applied at module import time (module-level side effects); no explicit init() call required
- Default model reads from environment variable (`LITELLM_MODEL` or similar) when callers don't pass model=; callers will usually pass model= explicitly
- Validate `VERTEXAI_PROJECT` and `VERTEXAI_LOCATION` at import time — raise a clear, descriptive error immediately if missing; do not wait for first call

#### Token counting behavior
- Try litellm's token_counter() first
- If litellm doesn't recognize the model (e.g. `vertex_ai/` prefix not in its registry), fall back to tiktoken `cl100k_base` tokenizer as a reasonable approximation
- `count_tokens(model, text)` signature — model arg kept so future dispatch (if needed) is possible

#### Error handling
- Let litellm exceptions bubble up raw — no translation to FastCode-specific types
- No logging inside llm_client — completely silent on success and failure; callers own their logging

### Claude's Discretion
- Exact env var name for default model (`LITELLM_MODEL`, `FASTCODE_MODEL`, etc.)
- Whether to log a warning (not error) when falling back to cl100k for token counting
- Module docstring and inline comments

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Centralized `fastcode/llm_client.py` module exposes `completion()` and `completion_stream()` via litellm | litellm.completion(model, messages, **kwargs) is the direct call; streaming via completion(stream=True) returning CustomStreamWrapper |
| INFRA-02 | litellm globals set at startup: `drop_params=True`, `suppress_debug_info=True` | Both are valid boolean module attributes on installed litellm 1.81.14; assignable at module level |
| INFRA-03 | `llm_utils.py` deleted — its functionality replaced by litellm param handling | llm_utils.py only contains openai_chat_completion() (max_tokens fallback); litellm.drop_params=True makes this unnecessary |
| INFRA-04 | Fallback/retry configuration via litellm's built-in retry logic | CONTEXT.md says "new capabilities (retry logic) are out of scope"; only the global settings (drop_params, suppress_debug_info) are in scope for this phase |
| TOKN-01 | `count_tokens()` in `utils.py` uses `litellm.token_counter()` instead of direct tiktoken | litellm.token_counter(model, text=) works with vertex_ai/ prefix out of the box on 1.81.14 — no KeyError observed |
</phase_requirements>

## Summary

Phase 2 creates `fastcode/llm_client.py` as the single import point for all LLM calls in FastCode. The module wraps litellm's `completion()` and provides a `count_tokens()` function that uses litellm's tokenizer with a tiktoken fallback. It also deletes `fastcode/llm_utils.py`, whose only function (`openai_chat_completion`) becomes unnecessary once `litellm.drop_params = True` is set globally.

The installed litellm version (1.81.14) handles `vertex_ai/` model name prefixes in `token_counter()` without raising `KeyError` — verified empirically. This means the tiktoken fallback the user specified may never trigger in practice, but it remains a good defensive pattern for truly unknown model strings. The `litellm.suppress_debug_info` and `litellm.drop_params` attributes are standard boolean module attributes and work as module-level side effects.

There is one important signature discrepancy to plan for: the existing `utils.py:count_tokens(text, model)` takes arguments in `(text, model)` order, but the new `llm_client.count_tokens(model, text)` reverses this. Callers in `answer_generator.py` currently call `count_tokens(prompt, self.model)` — they will need updating when Phase 3 migrates them. This phase only adds the new function to `llm_client.py`; it does NOT change `utils.py` (that stays for callers not yet migrated).

**Primary recommendation:** Create `fastcode/llm_client.py` with module-level globals, three exported functions (`completion`, `completion_stream`, `count_tokens`), and env-var validation at import time. Delete `llm_utils.py`. Touch nothing else.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| litellm | >=1.80.8 (installed: 1.81.14) | Unified LLM client, token counting | Already in requirements.txt; ADC/VertexAI tested in Phase 1 |
| tiktoken | already installed | Fallback tokenizer for cl100k_base | Already in requirements.txt; used by existing utils.py |
| python-dotenv | already installed | Load .env at test time | Already used in smoke tests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| os (stdlib) | stdlib | Read VERTEXAI_PROJECT, VERTEXAI_LOCATION env vars | Import-time validation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| litellm.token_counter() | direct tiktoken | Would miss native Gemini tokenizer if litellm gains it; current approach is future-proof |
| Module-level side effects | explicit init() function | CONTEXT.md locked this: module import sets globals, no init() needed |

**Installation:** No new packages needed — litellm[google] and tiktoken are already in requirements.txt.

## Architecture Patterns

### Recommended Project Structure
```
fastcode/
├── llm_client.py    # NEW: centralized LLM module (this phase)
├── utils.py         # UNCHANGED: keep count_tokens(text, model) for now
├── llm_utils.py     # DELETE: only openai_chat_completion(), replaced by drop_params
├── answer_generator.py  # UNCHANGED this phase (Phase 4 migrates this)
└── ...
```

### Pattern 1: Module-Level Global Configuration
**What:** Set litellm global attributes at the top level of `llm_client.py`, outside any function. These execute once when the module is first imported and persist for the process lifetime.
**When to use:** Required by CONTEXT.md decision — `drop_params=True`, `suppress_debug_info=True` must be set at startup, not per-call.
**Example:**
```python
# Source: verified against litellm 1.81.14 installed package
import litellm

litellm.drop_params = True
litellm.suppress_debug_info = True
```

### Pattern 2: Import-Time Environment Validation
**What:** Validate required env vars at module import time and raise immediately with a clear error message.
**When to use:** Required by CONTEXT.md — `VERTEXAI_PROJECT` and `VERTEXAI_LOCATION` must be validated at import, not at first call.
**Example:**
```python
import os

_project = os.environ.get("VERTEXAI_PROJECT")
_location = os.environ.get("VERTEXAI_LOCATION")

if not _project:
    raise EnvironmentError(
        "VERTEXAI_PROJECT environment variable is not set. "
        "Set it to your GCP project ID before importing fastcode.llm_client."
    )
if not _location:
    raise EnvironmentError(
        "VERTEXAI_LOCATION environment variable is not set. "
        "Set it to your GCP region (e.g. 'us-central1') before importing fastcode.llm_client."
    )
```

### Pattern 3: Thin Wrapper Functions
**What:** `completion()` and `completion_stream()` are thin pass-throughs to litellm — they just call `litellm.completion()` with the appropriate `stream` argument.
**When to use:** CONTEXT.md locked this — no wrapping of responses, callers handle exceptions and iterate chunks directly.
**Example:**
```python
# Source: litellm docs + verified signature
from litellm import completion as _litellm_completion

def completion(model: str, messages: list, **kwargs):
    """Thin pass-through to litellm.completion()."""
    return _litellm_completion(model=model, messages=messages, **kwargs)

def completion_stream(model: str, messages: list, **kwargs):
    """Thin pass-through to litellm.completion() with stream=True."""
    return _litellm_completion(model=model, messages=messages, stream=True, **kwargs)
```

### Pattern 4: Token Counting with Fallback
**What:** Call `litellm.token_counter()` first; catch `Exception` and fall back to tiktoken `cl100k_base`.
**When to use:** Required by CONTEXT.md. Note: empirical testing shows litellm 1.81.14 handles `vertex_ai/*` model names without error, so fallback may not trigger in practice. Keep it anyway for safety.
**Example:**
```python
# Source: verified against litellm 1.81.14 + CONTEXT.md decision
import tiktoken
from litellm import token_counter as _litellm_token_counter

def count_tokens(model: str, text: str) -> int:
    """Count tokens using litellm, falling back to cl100k_base for unknown models."""
    try:
        return _litellm_token_counter(model=model, text=text)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text, disallowed_special=()))
```

### Anti-Patterns to Avoid
- **Per-call global configuration:** Do NOT set `litellm.drop_params` inside `completion()`. Set once at module import level.
- **Exception translation:** Do NOT catch litellm exceptions and re-raise as FastCode types. CONTEXT.md locked: exceptions bubble raw.
- **Logging inside llm_client:** Do NOT add any logging. CONTEXT.md locked: completely silent module.
- **Wrapping streaming responses:** Do NOT wrap `CustomStreamWrapper` in a FastCode iterator. Return the litellm iterator directly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Max-tokens parameter fallback | openai_chat_completion() in llm_utils.py | litellm.drop_params=True | litellm silently drops unsupported params when drop_params=True |
| Provider dispatch (if/else on provider) | Custom routing logic | litellm model string prefix (vertex_ai/) | litellm routes by prefix automatically |
| Token counting for Gemini/VertexAI | Custom Gemini tokenizer | litellm.token_counter() | Already handles vertex_ai/ prefix in 1.81.14 |

**Key insight:** `llm_utils.py` exists solely because the old direct OpenAI client needed manual `max_tokens` / `max_completion_tokens` fallback. `litellm.drop_params = True` eliminates this entirely — the entire file can be deleted.

## Common Pitfalls

### Pitfall 1: Import-Time Validation Breaks Tests
**What goes wrong:** Import-time `EnvironmentError` on missing `VERTEXAI_PROJECT` causes test collection failures for unrelated tests.
**Why it happens:** Any `import fastcode.llm_client` in a test file triggers validation immediately, even if the test doesn't use LLM calls.
**How to avoid:** Phase 2 only creates `llm_client.py` — it is NOT imported by `__init__.py` yet (that happens when callers are migrated in Phase 3/4). Tests that need to import `llm_client` directly should use `monkeypatch.setenv()` or set env vars in `conftest.py`. The existing smoke test pattern (skip when VERTEXAI_PROJECT unset) can be extended.
**Warning signs:** `ImportError` or `EnvironmentError` in pytest collection output.

### Pitfall 2: Signature Mismatch with Existing Callers
**What goes wrong:** `answer_generator.py` calls `count_tokens(prompt, self.model)` — positional `(text, model)` order. The new `llm_client.count_tokens(model, text)` reverses this. Calling the wrong one silently passes a model string as text and vice versa.
**Why it happens:** CONTEXT.md says new function has `(model, text)` signature; existing `utils.count_tokens` has `(text, model)`. They coexist in the codebase until Phase 3/4 migrates callers.
**How to avoid:** Keep `utils.count_tokens(text, model)` unchanged in this phase. Do NOT update callers yet. Document the signature difference clearly in `llm_client.py` docstring.
**Warning signs:** Token counts that are wildly wrong (a model name string tokenized instead of actual text).

### Pitfall 3: suppress_debug_info Is Separate from Logging
**What goes wrong:** Developers expect `suppress_debug_info=True` to silence all litellm output but still see some INFO logs.
**Why it happens:** `suppress_debug_info` suppresses litellm's internal startup/version banner, not all logging. Python's logging framework is separate.
**How to avoid:** `suppress_debug_info=True` is correct for this use case (confirmed it exists as a module attribute in 1.81.14). If additional silence is needed, set `litellm.set_verbose = False` (default is already False).

### Pitfall 4: INFRA-04 Scope Ambiguity
**What goes wrong:** REQUIREMENTS.md says INFRA-04 is "Fallback/retry configuration via litellm's built-in retry logic" — but CONTEXT.md explicitly says "new capabilities (retry logic, observability, multi-provider dispatch) are out of scope for this phase."
**Why it happens:** Requirements were written before the scoping discussion narrowed Phase 2.
**How to avoid:** INFRA-04 in Phase 2 means only: `drop_params=True` and `suppress_debug_info=True` global settings are set (litellm's built-in retry defaults remain active; no explicit retry config is added). Do NOT build retry configuration — that is a v2 feature.

## Code Examples

Verified patterns from official sources and empirical testing:

### Complete llm_client.py Structure
```python
# Source: litellm 1.81.14 + CONTEXT.md decisions + empirical testing
"""
Centralized LLM client for FastCode.

All LLM call sites import from this module. litellm globals are set at
import time as module-level side effects — no explicit init() call required.

Exports:
    completion(model, messages, **kwargs) -> ModelResponse
    completion_stream(model, messages, **kwargs) -> CustomStreamWrapper
    count_tokens(model, text) -> int
"""
import os

import litellm
import tiktoken
from litellm import completion as _completion
from litellm import token_counter as _token_counter

# --- Module-level configuration (applied once at import) ---
litellm.drop_params = True
litellm.suppress_debug_info = True

# --- Environment validation (fail fast, not at first call) ---
_project = os.environ.get("VERTEXAI_PROJECT")
_location = os.environ.get("VERTEXAI_LOCATION")

if not _project:
    raise EnvironmentError(
        "VERTEXAI_PROJECT is not set. "
        "Export it before importing fastcode.llm_client."
    )
if not _location:
    raise EnvironmentError(
        "VERTEXAI_LOCATION is not set. "
        "Export it before importing fastcode.llm_client."
    )

# Default model (Claude's discretion: env var name)
DEFAULT_MODEL = os.environ.get("LITELLM_MODEL", "vertex_ai/gemini-2.0-flash-001")


def completion(model: str, messages: list, **kwargs):
    """Call litellm.completion() — exceptions bubble up raw."""
    return _completion(model=model, messages=messages, **kwargs)


def completion_stream(model: str, messages: list, **kwargs):
    """Call litellm.completion() with stream=True — returns CustomStreamWrapper."""
    return _completion(model=model, messages=messages, stream=True, **kwargs)


def count_tokens(model: str, text: str) -> int:
    """Count tokens via litellm; fall back to cl100k_base for unknown models.

    NOTE: Signature is (model, text) — reversed from utils.count_tokens(text, model).
    Callers migrating from utils.count_tokens must update argument order.
    """
    try:
        return _token_counter(model=model, text=text)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text, disallowed_special=()))
```

### Verified: token_counter Works with vertex_ai/ Prefix
```python
# Empirically verified on litellm 1.81.14 (2026-02-24)
from litellm import token_counter

# These ALL work without KeyError:
token_counter(model="vertex_ai/gemini-2.0-flash-001", text="Hello world")  # -> 2
token_counter(model="vertex_ai/gemini-1.5-pro",       text="Hello world")  # -> 2
token_counter(model="vertex_ai/gemini-3-flash-preview", text="Hello world") # -> 2
token_counter(model="vertex_ai/unknown-model-xyz",     text="Hello world")  # -> 2
```

### Global Attributes (verified on litellm 1.81.14)
```python
import litellm

litellm.drop_params = True          # Silently drops params unsupported by target model
litellm.suppress_debug_info = True  # Suppresses litellm startup/version banner
litellm.set_verbose = False         # Default; controls logging verbosity
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| openai_chat_completion() with max_tokens fallback | litellm.drop_params=True | litellm established pattern | llm_utils.py becomes dead code, can delete |
| Direct provider clients (openai.OpenAI, anthropic.Anthropic) | litellm.completion() with provider prefix | litellm 1.x | Single call path for all providers |
| tiktoken.encoding_for_model() for token counting | litellm.token_counter() | litellm 1.x | Falls back to tiktoken internally for unknown models |

**Deprecated/outdated:**
- `openai_chat_completion()` in llm_utils.py: drop_params=True makes the try/except hack unnecessary; delete entire file.
- `tiktoken.encoding_for_model(model)` with manual KeyError catch in utils.py: replaced by litellm.token_counter() — but utils.py stays unchanged until callers are migrated.

## Open Questions

1. **INFRA-04 exact scope**
   - What we know: REQUIREMENTS.md says "retry configuration via litellm's built-in retry logic"; CONTEXT.md says retry is out of scope
   - What's unclear: Does INFRA-04 just mean "set drop_params/suppress_debug_info" (the only globals in CONTEXT.md) or also set `litellm.num_retries`?
   - Recommendation: Treat INFRA-04 as fully satisfied by `drop_params=True` and `suppress_debug_info=True`. litellm's default retry behavior (litellm.retry=True by default) is already active without configuration. Do not add explicit retry config — that is v2 per STATE.md.

2. **Default model env var name**
   - What we know: CONTEXT.md gives Claude discretion on the exact name
   - What's unclear: `LITELLM_MODEL` vs `FASTCODE_MODEL` vs something else
   - Recommendation: Use `LITELLM_MODEL` — matches the library name, consistent with how litellm proxy uses it, and already mentioned in .env.example research.

3. **Warning on tiktoken fallback**
   - What we know: CONTEXT.md gives Claude discretion on whether to log a warning
   - What's unclear: Silence vs. warning is a debugging tradeoff
   - Recommendation: No warning. CONTEXT.md says "completely silent on success and failure." The fallback is a normal operation, not an error condition.

## Sources

### Primary (HIGH confidence)
- litellm 1.81.14 (installed) — empirically verified: `token_counter()` with `vertex_ai/` prefix, global attribute assignment, `completion` signature
- Context7 `/websites/litellm_ai` — `drop_params` global setting, `token_counter` API, streaming via `completion(stream=True)`
- Context7 `/berriai/litellm` — `token_counter` defaults to tiktoken for unknown models

### Secondary (MEDIUM confidence)
- Codebase inspection: `fastcode/llm_utils.py` (only `openai_chat_completion`), `fastcode/utils.py` (count_tokens signature and usage), `fastcode/answer_generator.py` (existing callers)

### Tertiary (LOW confidence)
- None — all critical claims verified empirically or via Context7

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed, versions confirmed empirically
- Architecture: HIGH — patterns verified against installed litellm 1.81.14
- Pitfalls: HIGH — signature mismatch discovered by direct code inspection; import-time validation pattern verified by existing smoke test pattern

**Research date:** 2026-02-24
**Valid until:** 2026-03-26 (stable library; litellm is fast-moving but global attrs are core API)
