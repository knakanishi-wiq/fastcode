# Phase 5: Fix answer_generator.py Wiring and Cleanup - Research

**Researched:** 2026-02-25
**Domain:** Python module wiring, litellm token counting, dependency cleanup
**Confidence:** HIGH

---

## Summary

Phase 5 is a surgical gap-closure phase. All four incomplete requirements (TOKN-01, STRM-01, STRM-02, STRM-03) share a single root cause: `answer_generator.py` was migrated in Phase 4 to call `llm_client.completion()` and `llm_client.completion_stream()`, but the surrounding wiring was not completed. Specifically, the file still imports `count_tokens` and `truncate_to_tokens` from `fastcode.utils` (tiktoken-based, old signature), `self.model` has no fallback when `MODEL` env var is unset, and the two CONF requirements have doc/dep tech debt from Phase 1 and 4.

The two CONF gaps (CONF-01, CONF-02) are independent file edits: remove `openai` and `anthropic` from `requirements.txt`, and add `LITELLM_MODEL` documentation plus a `vertex_ai/` prefix hint to `.env.example`. These require no code changes.

The TOKN-01 and STRM-01/02/03 gaps are entirely within `answer_generator.py`. The critical observations are: (1) `llm_client.count_tokens(model, text)` has the reversed argument order relative to `utils.count_tokens(text, model)` — every call site must flip the argument order when switching the import; (2) `truncate_to_tokens` does not exist in `llm_client` — `utils.truncate_to_tokens` uses tiktoken directly and will continue to be imported from `utils` (it is not a TOKN-01 target); (3) `self.model` must fall back to `llm_client.DEFAULT_MODEL` to match the pattern all other migrated files follow.

**Primary recommendation:** One plan (`05-01-PLAN.md`), three targeted edits: fix the import line and all six `count_tokens` call sites in `answer_generator.py`, add the `self.model` fallback in `__init__`, then clean `requirements.txt` and `.env.example`.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TOKN-01 | `count_tokens()` in `utils.py` uses `litellm.token_counter()` instead of direct tiktoken | Audit: `answer_generator.py` imports `count_tokens` from `fastcode.utils` (tiktoken). Fix: replace import with `from fastcode import llm_client` and change all 6 call sites from `count_tokens(text, model)` to `llm_client.count_tokens(model, text)`. |
| STRM-01 | `answer_generator.py` non-streaming `generate()` uses litellm via `llm_client` | Audit: wired at line 119 but `self.model` can be `None`. Fix: `self.model = os.getenv("MODEL") or llm_client.DEFAULT_MODEL` in `__init__`. |
| STRM-02 | `answer_generator.py` streaming `generate_stream()` uses litellm via `llm_client` | Same root cause as STRM-01: same `self.model` null risk applies to line 263. Same `__init__` fix resolves this. |
| STRM-03 | `_stream_with_summary_filter()` works correctly with litellm chunk format | Audit: chunk format `raw_chunk.choices[0].delta.content or ''` is correct. Only MODEL null risk remains. Same `__init__` fix resolves this. |
| CONF-01 | `requirements.txt` includes `litellm[google]` with version pin | Audit: `openai` and `anthropic` still listed at lines 32-33. Fix: remove both lines. `litellm[google]>=1.80.8` already present at line 35. |
| CONF-02 | `.env.example` documents VertexAI vars: `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`, model name format | Audit: `LITELLM_MODEL` not documented; `MODEL=your_model` lacks `vertex_ai/` prefix hint. Fix: add `LITELLM_MODEL=vertex_ai/gemini-2.0-flash-001` entry and update MODEL comment. |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| litellm | `>=1.80.8` (pinned in requirements.txt) | Token counting via `litellm.token_counter()` | Already the project's unified LLM client; `count_tokens` wraps it with tiktoken fallback |
| tiktoken | (already in requirements.txt) | Fallback in `llm_client.count_tokens` for unknown models | Kept as transitive dependency inside `llm_client.count_tokens` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `fastcode.utils.truncate_to_tokens` | — | Context truncation (tiktoken-based) | Continues to be used — no migration target for this phase |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `utils.truncate_to_tokens` (keep as-is) | `llm_client`-based truncation | `truncate_to_tokens` is NOT in scope for this phase. TOKN-01 only requires replacing `count_tokens`. Migrating `truncate_to_tokens` would be scope creep and is not referenced in any requirement. |

---

## Architecture Patterns

### Pattern 1: Import line change in answer_generator.py

**What:** Replace the `count_tokens` import from `utils` with use of the already-imported `llm_client` module.

**Current state (line 13):**
```python
from .utils import count_tokens, truncate_to_tokens
```

**After fix:**
```python
from .utils import truncate_to_tokens
```

`llm_client` is already imported at line 12:
```python
from fastcode import llm_client
```

So `count_tokens` calls become `llm_client.count_tokens(...)` — no new import needed.

### Pattern 2: Argument order reversal at all 6 call sites

**What:** `utils.count_tokens(text, model)` vs `llm_client.count_tokens(model, text)` — the argument order is reversed. Every call site must flip the arguments.

**Current (6 locations in answer_generator.py):**
```python
# Lines 75, 92, 113 in generate()
prompt_tokens = count_tokens(prompt, self.model)
base_tokens = count_tokens(system_prompt_sample, self.model)
final_prompt_tokens = count_tokens(prompt, self.model)

# Lines 206, 217, 232 in generate_stream()
prompt_tokens = count_tokens(prompt, self.model)
base_tokens = count_tokens(system_prompt_sample, self.model)
final_prompt_tokens = count_tokens(prompt, self.model)
```

**After fix:**
```python
prompt_tokens = llm_client.count_tokens(self.model, prompt)
base_tokens = llm_client.count_tokens(self.model, system_prompt_sample)
final_prompt_tokens = llm_client.count_tokens(self.model, prompt)
```

This pattern is identical for all 6 sites — two argument positions swap, `self.model` moves first.

### Pattern 3: MODEL env var fallback in __init__

**What:** Use `or llm_client.DEFAULT_MODEL` to match the pattern all other migrated files use.

**Current (line 43):**
```python
self.model = os.getenv("MODEL")
```

**After fix:**
```python
self.model = os.getenv("MODEL") or llm_client.DEFAULT_MODEL
```

`llm_client.DEFAULT_MODEL` is `os.environ.get("LITELLM_MODEL", "vertex_ai/gemini-2.0-flash-001")`. This gives users two override points: `MODEL` for `answer_generator.py`-specific override, `LITELLM_MODEL` for the global default.

### Pattern 4: requirements.txt — remove dead lines

**Current lines 32-33:**
```
openai
anthropic
```

**Action:** Remove both lines. No file in `fastcode/` imports either package. `litellm[google]>=1.80.8` on line 35 is the correct entry and is already present.

### Pattern 5: .env.example — add LITELLM_MODEL, fix MODEL hint

**Current:**
```
MODEL=your_model
```

**After fix (add LITELLM_MODEL and update MODEL comment):**
```
# Model used by answer_generator.py (override for streaming/non-streaming generation)
# Use vertex_ai/ prefix to route through VertexAI (ADC auth). Example:
MODEL=vertex_ai/gemini-2.0-flash-001

# Default model for all other LLM callers (query_processor, repo_selector, etc.)
# Reads LITELLM_MODEL; falls back to vertex_ai/gemini-2.0-flash-001 if unset
LITELLM_MODEL=vertex_ai/gemini-2.0-flash-001
```

### Anti-Patterns to Avoid

- **Migrating `truncate_to_tokens`:** This function is not a TOKN-01 target. `utils.truncate_to_tokens(text, max_tokens, model)` continues to be called from `_truncate_context()` at line 613. Do not change it.
- **Changing the `os` import:** `os` is still needed at line 43 for `os.getenv("MODEL")`. Do not remove it.
- **Removing `from fastcode import llm_client`:** This import is already at line 12 and used by `generate()`, `generate_stream()`, and `_stream_with_summary_filter()`. It stays.
- **Changing streaming chunk parsing:** The audit confirmed `raw_chunk.choices[0].delta.content or ""` is the correct litellm chunk format. Do not touch `_stream_with_summary_filter()` logic.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token counting for vertex_ai/ models | Custom tiktoken wrapper | `llm_client.count_tokens(model, text)` | Already implemented in Phase 2; uses `litellm.token_counter()` with tiktoken fallback |
| Model name fallback logic | Custom env-var resolution | `llm_client.DEFAULT_MODEL` | Already defined in `llm_client.py` line 43; consistent with all other migrated files |

---

## Common Pitfalls

### Pitfall 1: Forgetting to flip argument order at all 6 call sites
**What goes wrong:** If one of the 6 `count_tokens` calls is updated as `llm_client.count_tokens(prompt, self.model)` (old order), the model name ends up as the text being tokenized and the text ends up as the model name. `litellm.token_counter` will likely raise or return garbage.
**Why it happens:** The argument reversal is non-obvious; old calls read `count_tokens(text, model)` which looks natural.
**How to avoid:** Search for all `count_tokens(` occurrences in `answer_generator.py` before and after the edit. There are exactly 6. Verify each one reads `llm_client.count_tokens(self.model, <text_variable>)`.
**Warning signs:** A call where the first argument contains a long string (prompt text) rather than a short model identifier string.

### Pitfall 2: Leaving the `count_tokens` name in the import line
**What goes wrong:** If the import line is changed to `from .utils import truncate_to_tokens` but some call site still references bare `count_tokens`, Python raises `NameError: name 'count_tokens' is not defined` at runtime.
**How to avoid:** After removing `count_tokens` from the import, run `grep count_tokens fastcode/answer_generator.py` — all remaining matches must be `llm_client.count_tokens(`.

### Pitfall 3: Removing `truncate_to_tokens` from the import by mistake
**What goes wrong:** `_truncate_context()` (line 611-613) calls `truncate_to_tokens(context, max_tokens, self.model)` from `utils`. Removing this import breaks truncation.
**How to avoid:** The import line change is from `from .utils import count_tokens, truncate_to_tokens` to `from .utils import truncate_to_tokens` — `truncate_to_tokens` stays in the import.

### Pitfall 4: MODEL env var vs LITELLM_MODEL confusion in .env.example
**What goes wrong:** Users set `MODEL=gemini-2.0-flash` (without `vertex_ai/` prefix) and unknowingly route to Google AI Studio instead of VertexAI. This was already noted in the audit.
**How to avoid:** The `.env.example` update must include the `vertex_ai/` prefix in the example value AND a comment explaining the prefix requirement.

---

## Code Examples

### Verified current state — import line (answer_generator.py line 13)
```python
# Source: /Users/knakanishi/Repositories/FastCode/fastcode/answer_generator.py line 13
from .utils import count_tokens, truncate_to_tokens
```

### Verified target state — import line (after fix)
```python
from .utils import truncate_to_tokens
# count_tokens now accessed via already-imported llm_client module (line 12)
```

### Verified current state — __init__ (answer_generator.py line 43)
```python
# Source: /Users/knakanishi/Repositories/FastCode/fastcode/answer_generator.py line 43
self.model = os.getenv("MODEL")
```

### Verified target state — __init__ (after fix)
```python
self.model = os.getenv("MODEL") or llm_client.DEFAULT_MODEL
```

### Verified llm_client.count_tokens signature (llm_client.py lines 59-69)
```python
# Source: /Users/knakanishi/Repositories/FastCode/fastcode/llm_client.py
def count_tokens(model: str, text: str) -> int:
    """Count tokens via litellm; fall back to cl100k_base for unknown models.

    NOTE: Signature is (model, text) — reversed from utils.count_tokens(text, model).
    """
    try:
        return _token_counter(model=model, text=text)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text, disallowed_special=()))
```

### Verified llm_client.DEFAULT_MODEL (llm_client.py line 43)
```python
# Source: /Users/knakanishi/Repositories/FastCode/fastcode/llm_client.py
DEFAULT_MODEL: str = os.environ.get("LITELLM_MODEL", "vertex_ai/gemini-2.0-flash-001")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `count_tokens(text, model)` from utils (tiktoken) | `llm_client.count_tokens(model, text)` (litellm + tiktoken fallback) | Phase 2 (TOKN-01) | Accurate token counts for vertex_ai/ models |
| `self.model = os.getenv("MODEL")` — nullable | `self.model = os.getenv("MODEL") or llm_client.DEFAULT_MODEL` | Phase 5 (STRM-01/02/03) | Eliminates `litellm.completion(model=None)` runtime error |
| `openai` and `anthropic` in requirements.txt | Removed | Phase 5 (CONF-01) | Eliminates dead dependencies; reduces install size |
| `MODEL=your_model` without prefix hint in .env.example | `MODEL=vertex_ai/...` with prefix comment and `LITELLM_MODEL` entry | Phase 5 (CONF-02) | New users discover VertexAI routing correctly |

**Deprecated/outdated:**
- `utils.count_tokens(text, model)` — remains in `utils.py` for `indexer.py` (unused import there) and any future callers; NOT deleted. Only `answer_generator.py`'s usage is migrated.

---

## Open Questions

1. **Should `utils.count_tokens` be deleted or deprecated?**
   - What we know: `indexer.py` imports it but never calls it (import-only, dead usage). No other file calls it after `answer_generator.py` migrates.
   - What's unclear: Whether `utils.count_tokens` has any external callers outside `fastcode/`.
   - Recommendation: Leave `utils.count_tokens` in place for this phase. Deleting it is out of scope for Phase 5. The phase goal is wiring `answer_generator.py`, not cleaning up `utils.py`.

2. **Should `truncate_to_tokens` in utils also be migrated to use litellm?**
   - What we know: It uses tiktoken directly, same as `utils.count_tokens`. Not referenced in any requirement.
   - Recommendation: Out of scope for Phase 5. The roadmap has no requirement covering `truncate_to_tokens` migration.

3. **Does `indexer.py`'s dead `count_tokens` import need cleanup?**
   - What we know: `fastcode/indexer.py` line 15 imports `count_tokens` from utils but never calls it.
   - Recommendation: Out of scope for Phase 5. It is inert and does not affect correctness.

---

## Validation Architecture

> `workflow.nyquist_validation` is not present in `.planning/config.json` (only `workflow.research`, `workflow.plan_check`, `workflow.verifier`, `workflow.auto_advance` are configured). Nyquist validation is not enabled for this project. Skipping this section.

---

## Sources

### Primary (HIGH confidence)
- Direct file read: `/Users/knakanishi/Repositories/FastCode/fastcode/answer_generator.py` — current import line, all 6 count_tokens call sites, `__init__` model assignment, streaming chunk format
- Direct file read: `/Users/knakanishi/Repositories/FastCode/fastcode/llm_client.py` — `count_tokens(model, text)` signature, `DEFAULT_MODEL` definition
- Direct file read: `/Users/knakanishi/Repositories/FastCode/fastcode/utils.py` — `count_tokens(text, model)` (old) signature, `truncate_to_tokens` signature
- Direct file read: `/Users/knakanishi/Repositories/FastCode/requirements.txt` — confirmed `openai` and `anthropic` at lines 32-33, `litellm[google]>=1.80.8` at line 35
- Direct file read: `/Users/knakanishi/Repositories/FastCode/.env.example` — confirmed `MODEL=your_model` without prefix hint, `LITELLM_MODEL` absent
- Direct file read: `/Users/knakanishi/Repositories/FastCode/.planning/v1.0-MILESTONE-AUDIT.md` — audit findings with exact line numbers, root cause analysis, tech debt items
- Direct file read: `/Users/knakanishi/Repositories/FastCode/.planning/ROADMAP.md` — Phase 5 success criteria (5 items)
- Direct file read: `/Users/knakanishi/Repositories/FastCode/.planning/REQUIREMENTS.md` — requirement definitions and traceability status

### Secondary (MEDIUM confidence)
- None needed — this is a pure internal codebase wiring task with no external library research required.

### Tertiary (LOW confidence)
- None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in the codebase, verified by direct file reads
- Architecture: HIGH — all changes are mechanical edits to specific lines, verified against actual file content
- Pitfalls: HIGH — argument order reversal documented in llm_client.py module docstring and Phase 02 SUMMARY; verified by direct inspection

**Research date:** 2026-02-25
**Valid until:** Until any changes are made to `llm_client.py`, `utils.py`, or `answer_generator.py` — these are stable files. Research valid indefinitely for this phase scope.
