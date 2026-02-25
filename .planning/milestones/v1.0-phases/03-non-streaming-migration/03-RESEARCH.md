# Phase 3: Non-Streaming Migration - Research

**Researched:** 2026-02-24
**Domain:** Python LLM client migration — litellm, VertexAI, OpenAI/Anthropic API replacement
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Migration Sequencing**
- Migrate one file at a time — not all at once
- `query_processor.py` is migrated first (most critical code path)
- No fixed order for the remaining three files — let the planner assess and decide based on code analysis
- Each migrated file gets its own commit (one commit per file, not a single batched commit)

**Gemini System Message Handling**
- Use litellm's built-in conversion — trust the abstraction layer to handle Gemini's lack of a `system` role
- Pass conversation history as-is to `llm_client`; do not pre-process or filter roles at the call site
- If a Gemini system message error occurs at runtime, fail hard with a clear error — do not silently degrade or retry without the system message
- Researcher must verify the exact litellm behavior for Gemini system messages before planning (confirm the adapter handles it correctly)

**Cleanup Depth**
- Remove only what success criteria requires: direct provider imports (`openai`, `anthropic`) and provider dispatch branches (`if provider == "openai"`)
- Also remove function parameters that become unused after migration (e.g., `provider` args in function signatures) — dead parameters are confusing; update callers accordingly
- Check `requirements.txt` / `pyproject.toml` after migration — remove `openai` and `anthropic` packages if nothing else uses them after Phase 3

**Verification Approach**
- After each file migration: static check (grep confirms banned imports absent) + smoke test (run existing test suite)
- No new tests written per migrated file — existing tests serve as the regression guard
- After all 4 files are migrated: manual end-to-end test — send a real query through the API and verify a valid response routes through VertexAI

### Claude's Discretion
- Order of the 3 remaining files after `query_processor.py`
- Exact grep commands / CI steps used for the static import check

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MIGR-01 | `query_processor.py` uses litellm via `llm_client` instead of direct openai/anthropic calls | Codebase analysis confirms the file has `_initialize_llm_client()`, `_call_openai()`, `_call_anthropic()`, and `_resolve_references_and_rewrite()` — all replace with `llm_client.completion()` |
| MIGR-02 | `iterative_agent.py` uses litellm via `llm_client` instead of direct openai/anthropic calls | `_call_llm()` is the single LLM dispatch point — replace entire method; system message passes via messages list |
| MIGR-03 | `repo_overview.py` uses litellm via `llm_client` instead of direct openai/anthropic calls | `_summarize_readme_with_llm()` has inline openai/anthropic dispatch — replace with `llm_client.completion()` |
| MIGR-04 | `repo_selector.py` uses litellm via `llm_client` instead of direct openai/anthropic calls | `_call_openai()` and `_call_anthropic()` are thin wrappers — replace both with one `llm_client.completion()` call |
| MIGR-05 | Provider dispatch logic (`if provider == "openai"` branches) removed from all migrated files | Each file has `self.provider`, `self.api_key`, `self.anthropic_api_key`, `self.base_url` fields that go away entirely |
</phase_requirements>

---

## Summary

Phase 3 migrates four Python files off direct `openai`/`anthropic` clients and onto the centralized `fastcode.llm_client` module built in Phase 2. The work is mechanical but requires careful attention to three concerns: (1) collapsing the per-file provider dispatch into a single `llm_client.completion()` call, (2) verifying that litellm handles Gemini system messages transparently (confirmed — litellm converts `{"role": "system"}` to Gemini's `systemInstruction` field automatically when routing via the `vertex_ai/` prefix), and (3) removing the resulting dead code — constructor fields, function parameters, and potentially `openai`/`anthropic` packages from `requirements.txt`.

The most complex file is `iterative_agent.py` (~3200 lines). Its LLM calls all funnel through a single `_call_llm(prompt)` method (line 2472), which makes the migration surface-area well-defined despite the file size. The three simpler files (`query_processor.py`, `repo_overview.py`, `repo_selector.py`) each have thin `_call_openai()` / `_call_anthropic()` private methods that collapse into one `llm_client.completion()` call. Dead constructor state (`self.provider`, `self.api_key`, `self.anthropic_api_key`, `self.base_url`) must be removed from all four, and callers that pass a `provider` argument need to be updated in the same commit.

**Primary recommendation:** Migrate `query_processor.py` first (locked decision), then `repo_selector.py` and `repo_overview.py` (both tiny — ~200 lines of relevant code each), then `iterative_agent.py` last (most complex, largest surface area for regression).

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastcode.llm_client` | (project-local) | Centralized LLM calls via litellm | Built in Phase 2; all Phase 3 call sites replace direct clients with this |
| `litellm` | >=1.80.8 (pinned in requirements.txt) | OpenAI-compatible interface to VertexAI Gemini | Handles system message conversion, param dropping, auth |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | (pinned in requirements.txt) | Run existing regression suite after each file | After every file migration |

### Alternatives Considered

None applicable — all alternatives are locked out by decisions.

---

## Architecture Patterns

### Recommended Project Structure

No structural changes. All four files remain in `fastcode/`. The migration replaces the LLM call layer inside each file; the public class interfaces stay identical.

### Pattern 1: Collapse Provider Dispatch to Single llm_client Call

**What:** Replace the per-provider `_call_openai()` / `_call_anthropic()` private methods (and any inline dispatch blocks) with a direct call to `llm_client.completion()`.

**When to use:** Every LLM call site in the four target files.

**Example — before:**
```python
# repo_overview.py (before)
from openai import OpenAI
from anthropic import Anthropic
from .llm_utils import openai_chat_completion

def _call_openai(self, prompt):
    response = openai_chat_completion(
        self.llm_client,
        model=self.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=self.temperature,
        max_tokens=self.max_tokens,
    )
    return response.choices[0].message.content.strip()

def _call_anthropic(self, prompt):
    response = self.llm_client.messages.create(
        model=self.model,
        max_tokens=self.max_tokens,
        temperature=self.temperature,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()
```

**Example — after:**
```python
# repo_overview.py (after)
from fastcode import llm_client

def _call_llm(self, prompt: str) -> str:
    response = llm_client.completion(
        model=llm_client.DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=self.temperature,
        max_tokens=self.max_tokens,
    )
    return response.choices[0].message.content.strip()
```

### Pattern 2: System Message via messages List (iterative_agent.py)

**What:** The iterative agent passes a system message. Before migration it used OpenAI's `messages=[{"role": "system", ...}, {"role": "user", ...}]` pattern and Anthropic's separate `system=` parameter. After migration, pass the system message in the `messages` list; litellm converts it automatically for Gemini.

**Verification (HIGH confidence):** litellm official docs and code examples confirm that `messages=[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]` is fully supported for `vertex_ai/` models. litellm maps the `system` role to Gemini's `systemInstruction` field internally. No pre-processing needed at the call site.

**Example — after:**
```python
# iterative_agent.py _call_llm (after)
from fastcode import llm_client

def _call_llm(self, prompt: str) -> str:
    messages = [
        {"role": "system", "content": "You are a precise code analysis agent. Respond in specified format only."},
        {"role": "user", "content": prompt},
    ]
    response = llm_client.completion(
        model=llm_client.DEFAULT_MODEL,
        messages=messages,
        temperature=self.temperature,
        max_tokens=self.max_tokens,
    )
    if not response or not getattr(response, "choices", None):
        raise ValueError(f"Empty response: {response}")
    content = response.choices[0].message.content
    if not content:
        raise ValueError("No content in response")
    return content
```

### Pattern 3: Remove Dead Constructor State

**What:** After collapsing provider dispatch, these instance fields become dead code and must be removed:
- `self.provider`
- `self.api_key`
- `self.anthropic_api_key`
- `self.base_url`
- `self.model` (replaced by `llm_client.DEFAULT_MODEL` or the `LITELLM_MODEL` env var)
- `self.llm_client` / `self.client` (the old direct client reference)
- `self._initialize_llm_client()` / `self._initialize_client()` (the factory method)
- `load_dotenv()` call inside `__init__` (if used only to load LLM env vars that no longer apply)

**Important:** `self.model` specifically — in all four files it is set from `os.getenv("MODEL")`, which is the old provider-specific model name env var. After migration, the model is controlled by `LITELLM_MODEL` (defaults to `vertex_ai/gemini-2.0-flash-001` in `llm_client.py`). Remove `self.model` and use `llm_client.DEFAULT_MODEL` at each call site.

### Pattern 4: Caller Updates for Dead Parameters

**What:** Some methods accept a `provider` parameter from callers. If the parameter exists only to branch on `openai` vs `anthropic`, it becomes unused and should be removed from signatures. Callers must be updated in the same commit.

**Files that call the four targets:**
- `fastcode/main.py` instantiates `QueryProcessor`
- `fastcode/retriever.py` instantiates `RepositorySelector` (line 77) and `IterativeAgent` (line 1305)
- `fastcode/indexer.py` instantiates `RepositoryOverviewGenerator`
- `fastcode/__init__.py` imports all four

The constructors take a `config: Dict[str, Any]` argument and read `config.get("generation", {}).get("provider", "openai")`. After migration, the `provider` key in config is read only by migrated code — once all four files are done, config's `generation.provider` field becomes unused entirely. The planner should note that `config.yaml` cleanup (`generation.provider` removal) is Phase 4 scope (CONF-03), not Phase 3.

### Anti-Patterns to Avoid

- **Keeping `self.provider` as a no-op field:** Leaves dead code that implies branching still occurs. Remove it.
- **Using `os.getenv("MODEL")` after migration:** The old `MODEL` env var is provider-specific. After migration, `LITELLM_MODEL` governs the model. Do not read `MODEL` in migrated code.
- **Pre-filtering system messages before calling llm_client:** Contradicts the locked decision to trust litellm's conversion. Pass the messages list as-is.
- **Leaving `load_dotenv()` calls that load OpenAI/Anthropic keys:** After migration those keys are no longer needed. The `load_dotenv()` can remain if it also loads other vars (e.g., `VERTEXAI_PROJECT`), but `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` references should be removed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gemini system message conversion | Custom message pre-processor to strip/merge system messages | litellm built-in conversion | litellm maps `role: system` to Gemini `systemInstruction` automatically — confirmed by official docs and code examples |
| Provider dispatch logic | New branching logic | Remove entirely — `llm_client.completion()` is provider-agnostic | The whole point of Phase 3 is to eliminate dispatch |
| Model name lookup | New env var reader | `llm_client.DEFAULT_MODEL` | Already reads `LITELLM_MODEL` at import time |

**Key insight:** All three "custom solutions" listed above are exactly what the existing code has that needs to be removed. The right move is deletion, not replacement with a new custom version.

---

## Common Pitfalls

### Pitfall 1: Anthropic `system=` Parameter Incompatibility

**What goes wrong:** The Anthropic SDK uses a separate `system=` keyword argument in `client.messages.create()`, not a message in the `messages` list. litellm's OpenAI-compatible interface uses `messages` list only.

**Why it happens:** `iterative_agent.py`'s existing Anthropic branch (line 2502–2521) passes `system=` as a kwarg. If someone copies this pattern and passes `system=` to `llm_client.completion()`, it may or may not be forwarded correctly depending on litellm version. `drop_params=True` is set globally, so unknown params are dropped silently.

**How to avoid:** Always put the system message in the `messages` list with `{"role": "system", ...}`. Never pass `system=` as a kwarg to `llm_client.completion()`.

**Warning signs:** Response lacks persona/instructions despite system message being set.

### Pitfall 2: `self.model` Still Pointing to Old Provider Model Name

**What goes wrong:** After migration, `self.model` might still be set from `os.getenv("MODEL")`, which holds an OpenAI model name like `gpt-4-turbo-preview` or an Anthropic model name like `claude-3-5-sonnet-20241022`. Passing this to `llm_client.completion()` sends it to litellm, which will try to route based on the provider prefix in the model string.

**Why it happens:** `self.model = os.getenv("MODEL")` exists in all four files. It's easy to forget to remove it and switch to `llm_client.DEFAULT_MODEL`.

**How to avoid:** In each migrated file, delete `self.model = os.getenv("MODEL")` and use `llm_client.DEFAULT_MODEL` at each `completion()` call site. This makes the model selection consistent with the module-level default.

**Warning signs:** litellm error about unknown model, or unexpected routing to OpenAI/Anthropic instead of VertexAI.

### Pitfall 3: `llm_utils.openai_chat_completion` Import Left Behind

**What goes wrong:** `from .llm_utils import openai_chat_completion` is in all four files. `llm_utils.py` was deleted in Phase 2. If any migration leaves this import, the module fails to import entirely.

**Why it happens:** Forgetting to remove the import when replacing `_call_openai()` bodies.

**How to avoid:** The import removal is the first action in each file migration, not an afterthought.

**Warning signs:** `ModuleNotFoundError: No module named 'fastcode.llm_utils'` on import.

### Pitfall 4: `query_processor.py` Has Two Dispatch Sites

**What goes wrong:** `query_processor.py` has provider dispatch in two separate methods: `_enhance_with_llm()` (line 529) and `_resolve_references_and_rewrite()` (line 752). Missing the second site leaves a broken Anthropic branch.

**Why it happens:** The file is large (829 lines) and the second dispatch site is ~200 lines below the first.

**How to avoid:** Search for ALL occurrences of `self.provider` and `_call_openai` / `_call_anthropic` in each file before declaring migration complete.

**Warning signs:** Static grep check `grep -n "self.provider\|_call_openai\|_call_anthropic"` returns results after migration.

### Pitfall 5: `requirements.txt` Cleanup Timing

**What goes wrong:** Removing `openai` and `anthropic` from `requirements.txt` while `answer_generator.py` (Phase 4) still imports them breaks the Phase 4 start.

**Why it happens:** The decision says "check after Phase 3" but `answer_generator.py` is explicitly not migrated in Phase 3.

**How to avoid:** Before removing `openai` / `anthropic` from `requirements.txt`, grep ALL non-migrated files for their import. If `answer_generator.py` still imports `anthropic`/`openai`, keep the packages until Phase 4 completes.

**Warning signs:** `ImportError` on `answer_generator.py` import after removing packages.

---

## Code Examples

### Full Replacement Pattern: repo_selector.py `_call_openai` / `_call_anthropic`

Before (both methods, ~20 lines total):
```python
# Source: fastcode/repo_selector.py lines 189-208
def _call_openai(self, prompt: str) -> str:
    response = openai_chat_completion(
        self.llm_client,
        model=self.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=self.temperature,
        max_tokens=self.max_tokens,
    )
    return response.choices[0].message.content

def _call_anthropic(self, prompt: str) -> str:
    response = self.llm_client.messages.create(
        model=self.model,
        max_tokens=self.max_tokens,
        temperature=self.temperature,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

After (one method):
```python
# Source: project-specific pattern per llm_client.py interface
def _call_llm(self, prompt: str) -> str:
    response = llm_client.completion(
        model=llm_client.DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=self.temperature,
        max_tokens=self.max_tokens,
    )
    return response.choices[0].message.content
```

Call sites that previously called `_call_openai` or `_call_anthropic` are updated to call `_call_llm`.

### Full Replacement Pattern: iterative_agent.py `_call_llm`

Before (lines 2472–2524):
```python
def _call_llm(self, prompt: str) -> str:
    if self.provider == "openai":
        response = openai_chat_completion(
            self.client,
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a precise code analysis agent. Respond in specified format only."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        ...
        return content
    elif self.provider == "anthropic":
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system="You are a precise code analysis agent. Respond in specified format only.",
            messages=[{"role": "user", "content": prompt}]
        )
        ...
        return text
    else:
        raise ValueError(f"Unknown provider: {self.provider}")
```

After:
```python
def _call_llm(self, prompt: str) -> str:
    self.logger.info(f"Calling LLM: prompt_len={len(prompt)}, max_tokens={self.max_tokens}")
    response = llm_client.completion(
        model=llm_client.DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": "You are a precise code analysis agent. Respond in specified format only."},
            {"role": "user", "content": prompt},
        ],
        temperature=self.temperature,
        max_tokens=self.max_tokens,
    )
    if not response or not getattr(response, "choices", None):
        raise ValueError(f"Empty response: {response}")
    content = response.choices[0].message.content
    if not content:
        raise ValueError("No content in response")
    return content
```

### Static Import Check (grep command, Claude's Discretion)

After migrating each file, verify:
```bash
grep -n "from openai\|from anthropic\|import openai\|import anthropic\|from .llm_utils\|self\.provider\|_call_openai\|_call_anthropic" fastcode/<file>.py
```
Expected output: empty (no matches).

### Existing Test Run Command

```bash
pytest tests/test_llm_client.py -x -q
```

The existing test suite (`tests/test_llm_client.py`) tests the `llm_client` module contract with mocks — it does not require live VertexAI credentials. Run after each file migration.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct `OpenAI()` / `Anthropic()` clients in each file | `llm_client.completion()` via litellm | Phase 2 complete | Single auth path, single model selection point |
| `openai_chat_completion()` from `llm_utils.py` | Deleted in Phase 2 | Phase 2-02 | Import causes `ModuleNotFoundError` — must remove from all four files |
| `os.getenv("MODEL")` for model selection | `llm_client.DEFAULT_MODEL` (reads `LITELLM_MODEL`) | Phase 2 | Model now uses `vertex_ai/` prefix required by litellm VertexAI routing |
| `os.getenv("OPENAI_API_KEY")` / `ANTHROPIC_API_KEY` | ADC via `VERTEXAI_PROJECT` / `VERTEXAI_LOCATION` | Phase 1 | Old API key env vars no longer used by migrated code |

**Deprecated/outdated:**
- `from .llm_utils import openai_chat_completion`: module deleted — import must be removed from all four files
- `OpenAI()` / `Anthropic()` direct client instantiation: replaced by litellm routing
- `self.provider` field: removed from all four files post-migration (litellm handles routing transparently)

---

## Confirmed: litellm System Message Behavior for Gemini

**Confidence: HIGH** — Verified via Context7 against official litellm docs.

litellm fully supports passing `{"role": "system", "content": "..."}` in the `messages` list for `vertex_ai/` model strings. The library translates the OpenAI-format system message to Gemini's `systemInstruction` field internally. The call site does NOT need to convert or strip the system message.

Example from official docs (source: https://docs.litellm.ai/docs/providers/vertex):
```python
response = completion(
  model="vertex_ai/gemini-2.5-pro",
  messages=[
    {"content": "You are a good bot.", "role": "system"},
    {"content": "Hello, how are you?", "role": "user"}
  ],
)
```

This pattern maps directly to what `iterative_agent.py` needs after migration. No custom pre-processing is required at the call site.

---

## Recommended File Migration Order

Based on code analysis (Claude's Discretion per CONTEXT.md):

1. **`query_processor.py`** (locked first) — 829 lines, 2 dispatch sites (`_call_openai`/`_call_anthropic` called from `_enhance_with_llm` and `_resolve_references_and_rewrite`), `_initialize_llm_client()` factory to remove
2. **`repo_selector.py`** (~480 lines relevant) — smallest surface area; `_call_openai` and `_call_anthropic` are thin wrappers with no added logic; lowest regression risk
3. **`repo_overview.py`** (~280 lines) — single `_summarize_readme_with_llm()` dispatch site; slightly more logic (fallback to structure-based overview on error) but straightforward
4. **`iterative_agent.py`** (last) — ~3200 lines, 1 dispatch point (`_call_llm` at line 2472) but complex surrounding code; should be migrated last to reduce overall risk window

**Rationale:** Items 2 and 3 are low-risk warm-ups before tackling the complex `iterative_agent.py`. All three are independent (no import dependency on each other), so order within them is purely risk-management.

---

## Open Questions

1. **`requirements.txt` cleanup — can `openai` and `anthropic` be removed after Phase 3?**
   - What we know: `answer_generator.py` is Phase 4 and currently imports from both `openai` and `anthropic` (inferred from REQUIREMENTS.md and project state)
   - What's unclear: Whether any non-LLM code in the package depends on `openai`/`anthropic` types (e.g., type hints, data structures)
   - Recommendation: At end of Phase 3, grep all remaining non-migrated files for `openai` / `anthropic` imports before removing from `requirements.txt`. If `answer_generator.py` still uses them, defer to Phase 4.

2. **`config.yaml` `generation.provider` field — remove in Phase 3?**
   - What we know: CONF-03 (remove provider-specific config sections from `config.yaml`) is assigned to Phase 4
   - What's unclear: Whether any post-migration code in Phase 3 files still reads `config.get("generation", {}).get("provider")`
   - Recommendation: Leave `config.yaml` untouched in Phase 3. After removing `self.provider` from all four files, the config key becomes unused but harmless. Phase 4 removes it.

---

## Sources

### Primary (HIGH confidence)
- `/websites/litellm_ai` (Context7) — Gemini system message handling via `vertex_ai/` prefix, confirmed `{"role": "system"}` in messages list is supported
- `/berriai/litellm` (Context7) — VertexAI completion examples with system messages, `drop_params=True` behavior
- `fastcode/llm_client.py` — Verified interface: `completion(model, messages, **kwargs)`, `DEFAULT_MODEL`, `drop_params=True` global
- `fastcode/iterative_agent.py` lines 2472–2524 — Confirmed single `_call_llm()` dispatch point
- `fastcode/query_processor.py` — Confirmed 2 dispatch sites (lines 529 and 752)
- `fastcode/repo_overview.py` — Confirmed 1 dispatch site in `_summarize_readme_with_llm()`
- `fastcode/repo_selector.py` — Confirmed 2 thin wrapper methods `_call_openai` / `_call_anthropic`

### Secondary (MEDIUM confidence)
- `config/config.yaml` — Confirmed `generation.provider: "openai"` is currently set; Phase 3 migrated files will stop reading this key

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — llm_client.py interface is the project's own code, fully readable
- Architecture: HIGH — all four target files read directly; call patterns documented with line numbers
- Pitfalls: HIGH for import/provider removal pitfalls (direct code evidence); MEDIUM for requirements.txt cleanup timing (requires runtime verification)
- Gemini system message: HIGH — confirmed via official litellm docs and Context7

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (litellm system message API is stable; project codebase is static until Phase 3 executes)
