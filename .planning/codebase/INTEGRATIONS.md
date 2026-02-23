# External Integrations

**Analysis Date:** 2026-02-24

## APIs & External Services

**LLM Providers (FastCode core):**
- OpenAI (or OpenAI-compatible) - Primary answer generation
  - SDK/Client: `openai` Python package
  - Auth: `OPENAI_API_KEY` env var
  - Base URL: `BASE_URL` env var (allows routing to OpenRouter, Ollama, etc.)
  - Model: `MODEL` env var (e.g., `gpt-4-turbo-preview`)
  - Usage: `fastcode/answer_generator.py` `AnswerGenerator._initialize_client()`
- Anthropic Claude - Secondary LLM option
  - SDK/Client: `anthropic` Python package
  - Auth: `ANTHROPIC_API_KEY` env var
  - Base URL: `BASE_URL` env var
  - Usage: `fastcode/answer_generator.py`, toggled via `generation.provider: "anthropic"` in `config/config.yaml`

**LLM Providers (Nanobot agent):**
- litellm abstraction layer used by nanobot for multi-provider routing
- Providers configured in `nanobot_config.json` under `providers`: anthropic, openai, openrouter, deepseek, groq, zhipu, dashscope, vllm, gemini, moonshot, aihubmix
- Default nanobot model: `google/gemini-3-flash-preview` (configurable via `NANOBOT_MODEL` env var)

**Sentence Transformers (HuggingFace Hub):**
- Model download at container build time: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Download triggered in `Dockerfile` via `SentenceTransformer(...)` pre-warm
- Runtime model: `fastcode/embedder.py` `CodeEmbedder`
- No API key required; models downloaded from HuggingFace Hub

**OpenRouter (optional):**
- Used as OpenAI-compatible proxy when `BASE_URL=https://openrouter.ai/api/v1`
- Allows access to multiple LLM providers via single API key
- Configured via `OPENAI_API_KEY` + `BASE_URL` in `.env`

**Ollama (optional local):**
- Local LLM runtime configured with `BASE_URL=http://localhost:11434/v1`
- Example from `env.example`: model `qwen3-coder-30b_fastcode`

## Data Storage

**Vector Store:**
- FAISS (Facebook AI Similarity Search)
  - Index type: HNSW (`index_type: "HNSW"`)
  - Storage: local filesystem, `./data/vector_store/` (or Docker volume `./data`)
  - Files: `{repo_name}.faiss`, `{repo_name}_metadata.pkl`, `{repo_name}_bm25.pkl`, `{repo_name}_graphs.pkl`
  - Implemented in: `fastcode/vector_store.py`
  - No remote database; all vector data stored on disk

**Application Cache:**
- diskcache (default)
  - Storage: `./data/cache/` local directory
  - TTL: 1 hour for embeddings, 30 days for dialogue sessions
  - Implemented in: `fastcode/cache.py` `CacheManager`
- Redis (optional alternative)
  - Connection: `REDIS_HOST` (default: `localhost`), `REDIS_PORT` (default: `6379`)
  - Configured via `cache.backend: "redis"` in `config/config.yaml`

**Repository Source Code:**
- Local filesystem: `./repos/{repo_name}/` after cloning
- Git repositories cloned with depth=1 via gitpython: `fastcode/loader.py`
- ZIP uploads extracted to `./repos/{repo_name}/` via `api.py` `/upload-zip` endpoint

**Session / Dialogue History:**
- Stored in diskcache or Redis under keys `dialogue_{session_id}_turn_{n}` and `dialogue_session_{session_id}_index`
- 30-day TTL by default (`dialogue_ttl: 2592000`)

**Repository Overview Index:**
- Stored in `{persist_dir}/repo_overviews.pkl`
- Separate from main FAISS index; used for multi-repo routing

**Code Graphs:**
- Stored as `{repo_name}_graphs.pkl` in vector store directory
- Built using networkx: `fastcode/graph_builder.py`

## Authentication & Identity

**Auth Provider:**
- None - No user authentication implemented in FastCode API
- API is open (CORS: `allow_origins=["*"]`) - suitable for internal/containerized deployment only
- Nanobot channels use platform-native authentication (see Messaging Platforms below)

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry or similar)

**Logs:**
- Python `logging` module
- FastCode: file output to `./logs/fastcode.log` + console
- FastCode API: file output to `./logs/api.log` + console (configured in `api.py`)
- Log level: `INFO` default, configurable in `config/config.yaml` under `logging.level`
- Docker logs accessible via `docker compose logs -f`

## CI/CD & Deployment

**Hosting:**
- Docker Compose: two services (`fastcode` on port 8001, `nanobot` on port 18790/18791)
- `docker-compose.yml` at project root

**CI Pipeline:**
- Not detected (no `.github/workflows/`, CircleCI, etc.)

**FastCode API endpoints:**
- `GET /health` - Health check
- `GET /status` - System status with repo list
- `POST /load` - Load repo from URL or path
- `POST /load-and-index` - Load + index in one call
- `POST /upload-zip` - Upload ZIP file (max 100MB)
- `POST /upload-and-index` - Upload ZIP and index
- `POST /query` - Query repository (JSON response)
- `POST /query-stream` - Streaming query (Server-Sent Events)
- `GET /repositories` - List indexed repos
- `POST /load-repositories` - Load cached repos
- `POST /index-multiple` - Batch index multiple repos
- `POST /delete-repos` - Delete repos and indexes
- `GET /sessions` - List dialogue sessions
- `GET /session/{id}` - Get session history
- `DELETE /session/{id}` - Delete session
- `POST /new-session` - Create new session
- `POST /clear-cache` - Clear cache
- API docs: `http://host:8001/docs` (FastAPI auto-generated)

## Messaging Platforms (Nanobot)

**Feishu (Lark) - enabled by default in config:**
- SDK: `lark-oapi` Python package
- Channel implementation: `nanobot/nanobot/channels/feishu.py`
- Auth: `appId`, `appSecret`, `encryptKey`, `verificationToken` in `nanobot_config.json`

**Telegram:**
- SDK: `python-telegram-bot`
- Channel implementation: `nanobot/nanobot/channels/telegram.py`
- Auth: `token` in `nanobot_config.json`

**Discord:**
- Gateway WebSocket connection
- Channel implementation: `nanobot/nanobot/channels/discord.py`
- Auth: `token` in `nanobot_config.json`

**Slack:**
- SDK: `slack-sdk`
- Channel implementation: `nanobot/nanobot/channels/slack.py`

**DingTalk:**
- SDK: `dingtalk-stream`
- Channel implementation: `nanobot/nanobot/channels/dingtalk.py`

**WhatsApp:**
- Bridge via WebSocket: `nanobot/bridge/`
- Channel implementation: `nanobot/nanobot/channels/whatsapp.py`

**QQ:**
- SDK: `qq-botpy`
- Channel implementation: `nanobot/nanobot/channels/qq.py`

## Webhooks & Callbacks

**Incoming:**
- Messaging platform webhooks received by nanobot gateway (`0.0.0.0:18790`)
- Nanobot-to-FastCode communication via internal HTTP: `FASTCODE_API_URL=http://fastcode:8001` (Docker internal)

**Outgoing:**
- FastCode `/query-stream` sends Server-Sent Events (SSE) to web interface clients
- Nanobot calls FastCode API endpoints: `fastcode_load_repo`, `fastcode_query`, `fastcode_list_repos`, `fastcode_status`, `fastcode_session` (tool calls defined in `nanobot/nanobot/skills/fastcode/SKILL.md`)

## Environment Configuration

**Required env vars (FastCode):**
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` - LLM API authentication
- `MODEL` - LLM model name

**Optional env vars (FastCode):**
- `BASE_URL` - Custom OpenAI-compatible API endpoint
- `REDIS_HOST` / `REDIS_PORT` - Redis cache (default: localhost:6379)

**Required env vars (Nanobot):**
- Messaging platform credentials in `nanobot_config.json` (appId, appSecret, tokens)
- `NANOBOT_MODEL` - Override default agent model (default: `google/gemini-3-flash-preview`)
- `FASTCODE_API_URL` - Internal FastCode API URL (set to `http://fastcode:8001` in Docker)

**Secrets location:**
- `.env` file at project root (mounted read-only into Docker: `.env:/app/.env:ro`)
- `nanobot_config.json` at project root (mounted read-only: `nanobot_config.json:/root/.nanobot/config.json:ro`)

---

*Integration audit: 2026-02-24*
