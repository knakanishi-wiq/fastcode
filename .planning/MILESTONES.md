# Milestones

## v1.0 LiteLLM Provider Migration (Shipped: 2026-02-25)

**Phases completed:** 5 phases, 10 plans | 70 files changed | +9,792 / −1,296 lines | 65 commits | 12 days

**Key accomplishments:**
1. Centralized `fastcode/llm_client.py` — single `completion()`, `completion_stream()`, `count_tokens()`, `DEFAULT_MODEL` path for all LLM callers
2. All 4 non-streaming callers migrated (`query_processor.py`, `repo_selector.py`, `repo_overview.py`, `iterative_agent.py`) — provider dispatch branches removed
3. `answer_generator.py` fully migrated: streaming, non-streaming, and all 6 token-counting call sites wired through litellm
4. `llm_utils.py` deleted; `litellm.drop_params = True` supersedes its max_tokens fallback logic
5. VertexAI ADC smoke test + streaming smoke test confirmed live via real GCP credentials (13/13 passing)
6. Token counting and context truncation accurate for Gemini models via `litellm.token_counter()`

**Archive:** `.planning/milestones/v1.0-ROADMAP.md`

---

