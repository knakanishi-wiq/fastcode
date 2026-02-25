# Phase 4: Streaming Migration and Finalization - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate `answer_generator.py`'s full LLM path (both streaming and non-streaming) from direct OpenAI/Anthropic clients to `llm_client`. Remove all provider-specific dispatch, client initialization, and credentials from the class. Clean up `config/config.yaml` and `.env.example` to remove provider-specific config. This phase does NOT change answer generation behavior — only the underlying LLM routing.

</domain>

<decisions>
## Implementation Decisions

### Constructor cleanup
- Delete `_initialize_client()`, `self.client`, `self.provider`, `self.api_key`, `self.anthropic_api_key`, `self.base_url` (the env-loaded one) entirely
- Keep `self.model = os.getenv("MODEL")` — still needed for token counting and llm_client calls
- Keep `load_dotenv()` — MODEL and VERTEXAI_* vars still come from .env, and ensures answer_generator works standalone in tests
- All credential handling is delegated to llm_client

### _stream_with_summary_filter approach
- Replace the provider dispatch (openai vs anthropic) with a single `llm_client.completion_stream()` call
- Keep existing buffering and regex tag detection logic intact — it's correct, and the chunk format change doesn't require it
- litellm normalizes output to OpenAI-compatible format (`chunk.choices[0].delta.content`), so chunk extraction stays the same
- Do NOT simplify the buffer-holding logic — keep it as-is to minimize risk

### generate() non-streaming path
- Delete `_generate_openai()` and `_generate_anthropic()` methods entirely (success criteria requires no such methods)
- Replace provider dispatch in `generate()` with a direct `llm_client.completion()` call
- Use the same defensive check pattern as Phase 3 migrations: check `response.choices`, then `response.choices[0].message.content`

### generate_stream() path
- Delete `_generate_openai_stream()` and `_generate_anthropic_stream()` methods entirely
- Replace provider dispatch in `generate_stream()` with `llm_client.completion_stream()` (same as _stream_with_summary_filter)

### Config cleanup
- Delete `generation.provider: "openai"` line from `config/config.yaml` entirely (no replacement, no comment)
- Update the NOTE comment in config.yaml from "model and base_url are read from environment variables (MODEL, BASE_URL)" to "model is read from MODEL env var"
- Remove `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `BASE_URL` from `.env.example` — keep only `MODEL` and `VERTEXAI_*` vars

### Claude's Discretion
- Exact litellm import style in answer_generator.py (import llm_client module vs specific functions)
- Whether to add a defensive None-guard for `delta.content` in the new stream extractor (litellm may emit finish-reason chunks with no content)
- Test structure and coverage approach

</decisions>

<specifics>
## Specific Ideas

- The migration should follow the exact same pattern as Phase 3 files (query_processor, iterative_agent, etc.) for consistency
- The `_stream_with_summary_filter` change is "swap the stream source, touch nothing else"
- Both `generate()` and `generate_stream()` have a provider dispatch that needs to go away — treat them symmetrically

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-streaming-migration-and-finalization*
*Context gathered: 2026-02-25*
