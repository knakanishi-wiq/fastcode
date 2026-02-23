# Technology Stack

**Analysis Date:** 2026-02-24

## Languages

**Primary:**
- Python 3.12 (Docker image: `python:3.12-slim-bookworm`) - All application code

**Secondary:**
- HTML/CSS/JavaScript - Web interface (`web_interface.html`)
- YAML - Configuration (`config/config.yaml`)
- JSON - Nanobot configuration (`nanobot_config.json`)

## Runtime

**Environment:**
- Python 3.12 (Docker target), Python 3.13 (local dev host)
- PyTorch used for device-accelerated embedding (CUDA / MPS / CPU auto-detection)
- macOS-specific parallelism guards: `TOKENIZERS_PARALLELISM=false`, `OMP_NUM_THREADS=1`

**Package Manager:**
- pip with `requirements.txt` (FastCode core)
- hatchling build backend for nanobot sub-package (`nanobot/pyproject.toml`)
- No lockfile detected (requirements.txt unpinned)

## Frameworks

**REST API:**
- FastAPI - Primary API server (`api.py`), Web app server (`web_app.py`)
- Uvicorn - ASGI server for FastAPI
- Flask + flask-cors - Secondary web framework (in requirements, not yet primary)
- Pydantic v2 - Request/response validation throughout API

**CLI:**
- Click - Command-line interface (`main.py`)

**Nanobot Agent Framework:**
- typer - CLI for nanobot
- litellm - Multi-provider LLM abstraction for nanobot
- websockets / websocket-client - Real-time communication bridge

**Testing:**
- pytest - Test runner
- pytest-asyncio - Async test support
- pytest-cov - Coverage reporting

**Build/Dev:**
- Docker + docker-compose - Container orchestration (`Dockerfile`, `docker-compose.yml`)
- hatchling - Package build for nanobot

## Key Dependencies

**Embedding / ML:**
- `sentence-transformers` - Code embedding generation; default model `paraphrase-multilingual-MiniLM-L12-v2` (470MB, multilingual)
- `torch` - Device management (CUDA/MPS/CPU detection in `fastcode/embedder.py`)
- `numpy` - Vector math and embedding operations

**Vector Search:**
- `faiss-cpu` - Primary vector index (HNSW configuration); files stored as `{repo_name}.faiss` in `./data/vector_store/`
- `chromadb` - Listed as dependency; not used in active code paths (FAISS is primary)
- `rank-bm25` (BM25Okapi) - Keyword search hybrid component in `fastcode/retriever.py`

**Code Parsing:**
- `tree-sitter` - Base parser engine
- `tree-sitter-python`, `tree-sitter-javascript`, `tree-sitter-typescript`, `tree-sitter-java`, `tree-sitter-go`, `tree-sitter-c`, `tree-sitter-cpp`, `tree-sitter-rust`, `tree-sitter-c-sharp` - Language grammars
- `libcst` - Concrete syntax tree library for Python

**LLM Integration:**
- `openai` - Primary LLM client (`fastcode/answer_generator.py`); OpenAI-compatible API
- `anthropic` - Secondary LLM client (Anthropic Claude support)
- `tiktoken` - Token counting for context window management

**Caching:**
- `diskcache` - Default disk-based cache backend (`fastcode/cache.py`)
- `redis` - Optional Redis cache backend (configurable via `REDIS_HOST`/`REDIS_PORT`)

**Graph & Retrieval:**
- `networkx` - Code dependency/call graph construction (`fastcode/graph_builder.py`)

**Repository Management:**
- `gitpython` - Git repository cloning and management (`fastcode/loader.py`)

**Infrastructure:**
- `pyyaml` - Configuration file parsing
- `python-dotenv` - `.env` file loading
- `pandas` - Data manipulation utilities
- `tqdm` - Progress bars during indexing
- `pathspec` - `.gitignore`-style pattern matching for file filtering

**Nanobot-specific:**
- `lark-oapi` - Feishu (Lark) platform SDK
- `python-telegram-bot` - Telegram channel
- `dingtalk-stream` - DingTalk channel
- `slack-sdk` - Slack channel
- `qq-botpy` - QQ channel

## Configuration

**Environment:**
- `.env` file loaded via python-dotenv at startup
- Required: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` (LLM provider)
- Required: `MODEL` (model name, e.g., `gpt-4-turbo-preview`, `google/gemini-3-flash-preview`)
- Optional: `BASE_URL` (OpenAI-compatible API base, e.g., OpenRouter, Ollama)
- Optional: `REDIS_HOST`, `REDIS_PORT` (if using Redis cache backend)
- Nanobot: `NANOBOT_MODEL` (agent reasoning model)
- Template provided: `env.example`

**Application Config:**
- `config/config.yaml` - Primary YAML config (repository settings, parser, embedding, retrieval weights, generation, caching)
- `nanobot_config.json` - Nanobot agent/channel/provider configuration
- Config is loaded at `FastCode.__init__()` from `config/config.yaml` or falls back to `FastCode._get_default_config()`

**Build:**
- `Dockerfile` - Python 3.12 slim image, pre-downloads embedding model layer
- `docker-compose.yml` - Two services: `fastcode` (port 8001) and `nanobot` (port 18791→18790)
- Data volumes: `./data`, `./repos`, `./logs` mounted as persistent

## Platform Requirements

**Development:**
- Python 3.11+ (nanobot requires 3.11+, FastCode targets 3.12)
- Git (required for repository cloning)
- Build tools (`build-essential`) for tree-sitter compilation
- CUDA / MPS optional (embedding auto-detects best device)

**Production:**
- Docker with Docker Compose
- FastCode API: `http://0.0.0.0:8001`
- Nanobot gateway: `http://0.0.0.0:18790`
- Persistent storage needed for `./data/vector_store/`, `./data/cache/`, `./repos/`, `./logs/`

---

*Stack analysis: 2026-02-24*
