# Codebase Structure

**Analysis Date:** 2026-02-24

## Directory Layout

```
FastCode/
├── main.py                      # CLI entry point (Click)
├── web_app.py                   # FastAPI web app + HTML frontend server
├── api.py                       # FastAPI REST-only API server
├── web_interface.html           # Single-page frontend UI (served by web_app.py)
├── requirements.txt             # Python dependencies for FastCode
├── Dockerfile                   # FastCode container (runs web_app.py)
├── docker-compose.yml           # Multi-service compose: fastcode + nanobot
├── env.example                  # Template for .env secrets
├── nanobot_config.json          # Nanobot runtime config (channels, model, etc.)
├── run_nanobot.sh               # Shell script to run nanobot locally
├── config/
│   └── config.yaml              # FastCode system configuration (all tunable params)
├── fastcode/                    # Core FastCode Python package
│   ├── __init__.py              # Package exports
│   ├── main.py                  # FastCode orchestrator class
│   ├── loader.py                # RepositoryLoader (git clone, zip, local path)
│   ├── parser.py                # CodeParser (Python AST via libcst, multi-lang)
│   ├── tree_sitter_parser.py    # Tree-sitter based parser for non-Python languages
│   ├── import_extractor.py      # Extract import statements from source files
│   ├── definition_extractor.py  # Extract symbol definitions
│   ├── call_extractor.py        # Extract function call relationships
│   ├── embedder.py              # CodeEmbedder (sentence-transformers)
│   ├── indexer.py               # CodeIndexer + CodeElement dataclass
│   ├── vector_store.py          # VectorStore (FAISS HNSW)
│   ├── graph_builder.py         # CodeGraphBuilder (NetworkX call/dep/inherit graphs)
│   ├── global_index_builder.py  # GlobalIndexBuilder (file/module/export maps)
│   ├── module_resolver.py       # ModuleResolver (dotted module path resolution)
│   ├── symbol_resolver.py       # SymbolResolver (symbol-to-node resolution)
│   ├── path_utils.py            # PathUtils (safe path normalization)
│   ├── retriever.py             # HybridRetriever (semantic + BM25 + graph)
│   ├── query_processor.py       # QueryProcessor (LLM query rewriting/expansion)
│   ├── repo_overview.py         # RepositoryOverviewGenerator (LLM summaries)
│   ├── repo_selector.py         # RepositorySelector (multi-repo LLM selection)
│   ├── iterative_agent.py       # IterativeAgent (confidence-based multi-round retrieval)
│   ├── agent_tools.py           # AgentTools (read-only file/dir exploration tools)
│   ├── answer_generator.py      # AnswerGenerator (OpenAI/Anthropic LLM)
│   ├── cache.py                 # CacheManager (diskcache or Redis)
│   ├── llm_utils.py             # Shared LLM utility functions
│   └── utils.py                 # General utilities (config, logging, hashing, etc.)
├── assets/                      # Static assets served by web_app.py at /assets
├── nanobot/                     # Nanobot AI assistant framework (separate Python package)
│   ├── pyproject.toml           # Nanobot package definition
│   ├── Dockerfile               # Nanobot container
│   ├── nanobot/                 # Nanobot Python source
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── agent/               # Core agent loop and tools
│   │   │   ├── loop.py          # AgentLoop (main processing engine)
│   │   │   ├── context.py       # ContextBuilder (system prompt + history assembly)
│   │   │   ├── memory.py        # Agent memory management
│   │   │   ├── skills.py        # Skill loader
│   │   │   ├── subagent.py      # SubagentManager (spawning child agents)
│   │   │   └── tools/           # LLM-callable tools
│   │   │       ├── base.py      # Abstract Tool base class
│   │   │       ├── registry.py  # ToolRegistry
│   │   │       ├── fastcode.py  # FastCode integration tools (HTTP to FastCode API)
│   │   │       ├── filesystem.py# File read/write/edit/list tools
│   │   │       ├── shell.py     # Shell exec tool
│   │   │       ├── web.py       # Web search/fetch tools
│   │   │       ├── message.py   # Send message tool
│   │   │       ├── spawn.py     # Spawn subagent tool
│   │   │       └── cron.py      # Schedule cron job tool
│   │   ├── bus/                 # Internal message bus
│   │   │   ├── events.py        # InboundMessage / OutboundMessage dataclasses
│   │   │   └── queue.py         # MessageBus (asyncio queue)
│   │   ├── channels/            # Messaging platform adapters
│   │   │   ├── base.py          # Abstract Channel base class
│   │   │   ├── manager.py       # ChannelManager
│   │   │   ├── telegram.py      # Telegram adapter
│   │   │   ├── slack.py         # Slack adapter
│   │   │   ├── discord.py       # Discord adapter
│   │   │   ├── dingtalk.py      # DingTalk adapter
│   │   │   ├── feishu.py        # Feishu/Lark adapter
│   │   │   ├── whatsapp.py      # WhatsApp adapter (uses Node.js bridge)
│   │   │   ├── qq.py            # QQ adapter
│   │   │   └── email.py         # Email adapter
│   │   ├── cli/                 # CLI commands
│   │   ├── config/              # Config schema (Pydantic)
│   │   ├── cron/                # Cron scheduler service
│   │   ├── heartbeat/           # Heartbeat/health service
│   │   ├── providers/           # LLM provider adapters
│   │   │   ├── base.py          # Abstract LLMProvider
│   │   │   ├── litellm_provider.py # LiteLLM-based provider
│   │   │   ├── registry.py      # Provider registry
│   │   │   └── transcription.py # Audio transcription support
│   │   ├── session/             # Session/conversation history management
│   │   ├── skills/              # Skill definitions (Markdown prompt files)
│   │   │   ├── README.md
│   │   │   ├── cron/            # Cron skill
│   │   │   ├── fastcode/        # FastCode skill (SKILL.md prompt)
│   │   │   ├── github/          # GitHub skill
│   │   │   ├── skill-creator/   # Meta-skill for creating new skills
│   │   │   ├── summarize/       # Summarization skill
│   │   │   ├── tmux/            # Tmux session skill
│   │   │   └── weather/         # Weather skill
│   │   └── utils/               # Nanobot utility functions
│   └── bridge/                  # WhatsApp Node.js bridge (TypeScript)
│       └── src/
│           ├── index.ts         # Entry point
│           ├── server.ts        # BridgeServer (WebSocket)
│           ├── whatsapp.ts      # WhatsAppClient (Baileys)
│           └── types.d.ts       # TypeScript type declarations
├── data/                        # Runtime data (gitignored)
│   ├── vector_store/            # FAISS indexes + metadata (per repo)
│   └── cache/                   # diskcache embeddings and dialogue history
├── repos/                       # Cloned/loaded repositories (gitignored)
└── logs/                        # Application logs (gitignored)
```

## Directory Purposes

**`fastcode/`:**
- Purpose: Core code intelligence package; the entire RAG pipeline lives here
- Contains: 26 Python modules organized by pipeline stage (ingestion → indexing → retrieval → generation)
- Key files: `fastcode/main.py` (orchestrator), `fastcode/retriever.py` (hybrid search), `fastcode/answer_generator.py` (LLM generation)

**`nanobot/`:**
- Purpose: Separate AI assistant framework; integrates with FastCode as an HTTP API client
- Contains: Full nanobot framework source, its own `pyproject.toml`, `Dockerfile`, TypeScript bridge
- Key files: `nanobot/nanobot/agent/loop.py` (core loop), `nanobot/nanobot/agent/tools/fastcode.py` (FastCode integration)

**`config/`:**
- Purpose: Static configuration for the FastCode system
- Contains: `config.yaml` with all tunable parameters (embedding model, retrieval weights, LLM settings, cache config)
- Key files: `config/config.yaml`

**`assets/`:**
- Purpose: Static files served by `web_app.py` at the `/assets` route
- Generated: No
- Committed: Yes

**`data/`:**
- Purpose: Runtime persistence for FAISS indexes, BM25 indexes, graph pickles, and diskcache
- Generated: Yes (at runtime)
- Committed: No (gitignored)

**`repos/`:**
- Purpose: Destination for cloned or locally loaded repositories
- Generated: Yes (at runtime, created by `RepositoryLoader`)
- Committed: No (gitignored)

## Key File Locations

**Entry Points:**
- `main.py`: CLI entry point — `python main.py query --query "..."`
- `web_app.py`: Web app entry point — `uvicorn web_app:app --host 0.0.0.0 --port 8001`
- `api.py`: API-only entry point — `uvicorn api:app --host 0.0.0.0 --port 8001`
- `nanobot/nanobot/cli/commands.py`: Nanobot CLI entry point — `nanobot gateway`

**Configuration:**
- `config/config.yaml`: All FastCode system parameters
- `env.example`: Template showing required environment variables (copy to `.env`)
- `nanobot_config.json`: Nanobot runtime config (channel tokens, model, skills)

**Core Logic:**
- `fastcode/main.py`: `FastCode` orchestrator — the single source of truth for pipeline wiring
- `fastcode/retriever.py`: `HybridRetriever` — the most complex module; handles all search strategies
- `fastcode/iterative_agent.py`: `IterativeAgent` — agentic multi-round retrieval loop
- `fastcode/answer_generator.py`: `AnswerGenerator` — LLM call with context assembly
- `nanobot/nanobot/agent/loop.py`: `AgentLoop` — nanobot's core processing engine

**Testing:**
- No test files detected in the repository at time of analysis

## Naming Conventions

**Files:**
- Snake_case Python modules: `query_processor.py`, `graph_builder.py`, `vector_store.py`
- Suffix by responsibility: `_extractor.py`, `_builder.py`, `_generator.py`, `_resolver.py`, `_utils.py`
- TypeScript files in `nanobot/bridge/src/` use camelCase: `server.ts`, `whatsapp.ts`

**Directories:**
- Snake_case for Python packages: `fastcode/`, `nanobot/`
- Lowercase for nanobot subpackages: `agent/`, `bus/`, `channels/`, `providers/`, `skills/`

**Classes:**
- PascalCase throughout: `FastCode`, `HybridRetriever`, `CodeElement`, `RepositoryLoader`, `AgentLoop`

**Config Keys:**
- Snake_case in YAML: `semantic_weight`, `enable_agency_mode`, `max_context_tokens`

## Where to Add New Code

**New retrieval strategy:**
- Implementation: `fastcode/retriever.py` — add method to `HybridRetriever`, combine score in `retrieve()`
- Config key: `config/config.yaml` under `retrieval:`

**New code element type:**
- Implementation: `fastcode/indexer.py` — add to `CodeIndexer.index_repository()`, update `CodeElement.type` values
- Parser support: `fastcode/parser.py` or `fastcode/tree_sitter_parser.py`

**New LLM provider (FastCode):**
- Implementation: `fastcode/answer_generator.py` and `fastcode/query_processor.py` — add elif branch in `_initialize_client()`
- Config: update `generation.provider` in `config/config.yaml`

**New API endpoint:**
- Implementation: `web_app.py` (for web + API) or `api.py` (API only) — add FastAPI route function
- Request/response models: add Pydantic `BaseModel` subclass at the top of the same file

**New nanobot channel:**
- Implementation: `nanobot/nanobot/channels/` — create new `<platform>.py` implementing the abstract `Channel` base class from `channels/base.py`
- Register: `nanobot/nanobot/channels/manager.py`

**New nanobot tool:**
- Implementation: `nanobot/nanobot/agent/tools/` — create new `<tool>.py` implementing `Tool` from `tools/base.py`
- Register: `nanobot/nanobot/agent/tools/registry.py` and wire into `AgentLoop` in `agent/loop.py`

**New nanobot skill:**
- Implementation: `nanobot/nanobot/skills/<skill-name>/SKILL.md` — Markdown file describing the skill to the LLM

**Shared utilities:**
- FastCode helpers: `fastcode/utils.py`
- FastCode path helpers: `fastcode/path_utils.py`
- Nanobot helpers: `nanobot/nanobot/utils/`

## Special Directories

**`data/vector_store/`:**
- Purpose: Persisted FAISS index files (`.index`), BM25 pickles, NetworkX graph pickles, and FAISS metadata JSON — one set of files per indexed repository
- Generated: Yes
- Committed: No

**`data/cache/`:**
- Purpose: `diskcache` directory for embedding cache and multi-turn dialogue history
- Generated: Yes
- Committed: No

**`repos/`:**
- Purpose: Working copies of all loaded repositories; `RepositoryLoader` clones into subdirectories here
- Generated: Yes
- Committed: No

**`nanobot/bridge/`:**
- Purpose: Self-contained Node.js/TypeScript WhatsApp bridge; has its own `package.json` and build pipeline separate from the Python codebase
- Generated: No (source committed)
- Committed: Yes

---

*Structure analysis: 2026-02-24*
