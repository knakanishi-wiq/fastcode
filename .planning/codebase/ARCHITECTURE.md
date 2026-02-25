# Architecture

**Analysis Date:** 2026-02-24

## Pattern Overview

**Overall:** Layered Pipeline Architecture with Dual-System Design

The codebase consists of two independent systems:
1. **FastCode** - A Python-based code intelligence backend (RAG pipeline + agentic retrieval)
2. **Nanobot** - A Python-based multi-channel AI assistant framework that integrates with FastCode via HTTP

Both systems are containerized and communicate via an internal HTTP API.

**Key Characteristics:**
- FastCode follows a strict linear pipeline: Load → Parse → Embed → Index → Retrieve → Generate
- Nanobot follows an event-driven message bus pattern: Channel → Bus → AgentLoop → LLM → Channel
- Separation of concerns between systems: FastCode exposes a REST API; Nanobot calls it as a tool
- Configuration-driven behavior: all tunable parameters in `config/config.yaml`
- The FastCode `FastCode` class (`fastcode/main.py`) is the single orchestrator that wires all pipeline components together

## Layers

**Presentation / Entry Layer:**
- Purpose: Accept user requests and return responses (HTTP REST, CLI, or web UI)
- Location: `main.py` (CLI), `web_app.py` (FastAPI web + HTML frontend), `api.py` (FastAPI REST-only)
- Contains: Click CLI commands, FastAPI route handlers, Pydantic request/response models
- Depends on: `fastcode/` package
- Used by: External clients, browsers, nanobot's `fastcode.py` tool

**Core Orchestration Layer:**
- Purpose: Coordinate all pipeline components for a query lifecycle
- Location: `fastcode/main.py` (class `FastCode`)
- Contains: Component initialization, `load_repository()`, `index_repository()`, `query()` methods
- Depends on: All components below
- Used by: Presentation layer

**Ingestion / Parsing Layer:**
- Purpose: Load code from source, parse it into structured elements
- Location: `fastcode/loader.py` (`RepositoryLoader`), `fastcode/parser.py` (`CodeParser`), `fastcode/tree_sitter_parser.py`, `fastcode/import_extractor.py`, `fastcode/definition_extractor.py`, `fastcode/call_extractor.py`
- Contains: Git cloning, zip extraction, AST parsing via `libcst` and `tree-sitter`, multi-language support
- Depends on: `fastcode/utils.py`
- Used by: `CodeIndexer`

**Indexing & Storage Layer:**
- Purpose: Convert parsed code into searchable `CodeElement` objects and persist them
- Location: `fastcode/indexer.py` (`CodeIndexer`, `CodeElement`), `fastcode/embedder.py` (`CodeEmbedder`), `fastcode/vector_store.py` (`VectorStore`), `fastcode/cache.py` (`CacheManager`)
- Contains: Multi-level indexing (file/class/function/documentation), sentence-transformer embeddings, FAISS HNSW vector store, disk/Redis cache
- Depends on: Ingestion layer, `fastcode/repo_overview.py`
- Used by: Retrieval layer

**Graph & Resolution Layer:**
- Purpose: Build structural relationships between code elements
- Location: `fastcode/graph_builder.py` (`CodeGraphBuilder`), `fastcode/global_index_builder.py` (`GlobalIndexBuilder`), `fastcode/module_resolver.py` (`ModuleResolver`), `fastcode/symbol_resolver.py` (`SymbolResolver`), `fastcode/path_utils.py` (`PathUtils`)
- Contains: NetworkX call/dependency/inheritance graphs, file-to-module map, symbol export map
- Depends on: Indexing layer
- Used by: Retrieval layer

**Retrieval Layer:**
- Purpose: Find relevant code elements for a user query using hybrid search
- Location: `fastcode/retriever.py` (`HybridRetriever`), `fastcode/query_processor.py` (`QueryProcessor`), `fastcode/repo_selector.py` (`RepositorySelector`), `fastcode/iterative_agent.py` (`IterativeAgent`), `fastcode/agent_tools.py` (`AgentTools`)
- Contains: Semantic (FAISS) + keyword (BM25) + graph traversal search, LLM-enhanced query rewriting, multi-repo two-stage selection, iterative agent with confidence-based stopping
- Depends on: Storage layer, Graph layer, LLM providers
- Used by: Orchestration layer

**Generation Layer:**
- Purpose: Produce natural language answers from retrieved context
- Location: `fastcode/answer_generator.py` (`AnswerGenerator`), `fastcode/llm_utils.py`
- Contains: OpenAI/Anthropic client, multi-turn dialogue context, token budget management, streaming support
- Depends on: Retrieval layer output
- Used by: Orchestration layer

**Nanobot Agent Framework (independent system):**
- Purpose: Multi-channel AI assistant with pluggable skills and tools
- Location: `nanobot/nanobot/`
- Contains: Message bus (`bus/`), channel adapters (`channels/`), agent loop (`agent/loop.py`), LLM providers (`providers/`), skills system (`skills/`), session management (`session/`), cron scheduler (`cron/`)
- Depends on: FastCode via HTTP (`FASTCODE_API_URL`)
- Used by: External chat channels (Telegram, Slack, DingTalk, Feishu, Discord, WhatsApp, QQ, email)

**WhatsApp Bridge (Node.js sidecar):**
- Purpose: Bridge WhatsApp Web protocol to Python via WebSocket
- Location: `nanobot/bridge/src/` (TypeScript)
- Contains: `BridgeServer` (WebSocket server), `WhatsAppClient` (Baileys-based WA client)
- Depends on: Nothing in the Python codebase
- Used by: `nanobot/nanobot/channels/whatsapp.py`

## Data Flow

**Query Flow (single-repo):**

1. User submits question via CLI (`main.py`), web API (`web_app.py`/`api.py`), or Nanobot
2. `FastCode.query()` in `fastcode/main.py` receives the question
3. `QueryProcessor.process()` in `fastcode/query_processor.py` expands and rewrites the query via LLM, extracts keywords and intent
4. `HybridRetriever.retrieve()` in `fastcode/retriever.py` executes:
   - Semantic search via FAISS (VectorStore)
   - Keyword search via BM25 (rank-bm25)
   - Graph traversal via NetworkX (CodeGraphBuilder)
   - Scores are combined with configurable weights (default: 0.5/0.5/1.0)
5. If agency mode is enabled, `IterativeAgent` in `fastcode/iterative_agent.py` refines retrieval iteratively using `AgentTools` (file read, dir list, search) until confidence threshold is met
6. `AnswerGenerator.generate()` in `fastcode/answer_generator.py` sends retrieved context + question to OpenAI/Anthropic LLM
7. Response returned as `Dict[str, Any]` with `answer`, `sources`, token counts

**Indexing Flow:**

1. `FastCode.load_repository()` triggers `RepositoryLoader` to clone/copy code to `./repos/`
2. `FastCode.index_repository()` calls `CodeIndexer.index_repository()`
3. `CodeParser` parses each file using `libcst` (Python) or tree-sitter (other languages)
4. `CodeEmbedder` generates sentence-transformer embeddings per code element
5. Embeddings added to `VectorStore` (FAISS HNSW index)
6. `GlobalIndexBuilder` builds file/module/export maps
7. `CodeGraphBuilder` builds call/dependency/inheritance graphs using NetworkX
8. BM25 index built in-memory by `HybridRetriever`
9. All artifacts persisted to `./data/vector_store/` and `./data/cache/`

**Nanobot Message Flow:**

1. Chat message arrives via a channel adapter (e.g., `channels/telegram.py`)
2. Channel puts an `InboundMessage` onto `MessageBus` (`bus/queue.py`)
3. `AgentLoop` (`agent/loop.py`) dequeues the message
4. `ContextBuilder` assembles system prompt + conversation history + skills
5. LLM called via `LiteLLM` provider (`providers/litellm_provider.py`)
6. If LLM calls a tool, `ToolRegistry` dispatches to the matching `Tool` instance (e.g., `FastCodeQueryTool`)
7. FastCode tool makes HTTP POST to `http://fastcode:8001/api/query`
8. Response assembled and sent back via `OutboundMessage` through the channel adapter

**State Management:**
- `FastCode` instance holds in-memory state: `repo_loaded`, `repo_indexed`, `loaded_repositories` dict (multi-repo mode), BM25 index, FAISS index
- Multi-turn dialogue history stored in `CacheManager` (disk or Redis), keyed by `session_id`
- Nanobot session history managed by `SessionManager` (`nanobot/nanobot/session/manager.py`)

## Key Abstractions

**CodeElement:**
- Purpose: Unified representation of any indexable code entity (file, class, function, docstring)
- Examples: `fastcode/indexer.py` (dataclass definition)
- Pattern: Dataclass with `id`, `type`, `name`, `file_path`, `language`, `code`, `metadata` fields; supports `to_dict()` for serialization

**HybridRetriever:**
- Purpose: Unifies three retrieval strategies into a single scored result list
- Examples: `fastcode/retriever.py`
- Pattern: Maintains separate FAISS (semantic), BM25 (keyword), and NetworkX (graph) indexes; combines scores with configurable weights; delegates to `IterativeAgent` in agency mode

**FastCode (orchestrator):**
- Purpose: Facade/coordinator that owns all component instances and exposes the public API
- Examples: `fastcode/main.py`
- Pattern: Single class instantiated by all entry points; initializes components in `__init__`, exposes `load_repository()`, `index_repository()`, `query()`, `list_repositories()` as the public interface

**Tool (nanobot):**
- Purpose: Abstract base for all LLM-callable tools in nanobot
- Examples: `nanobot/nanobot/agent/tools/base.py`, `nanobot/nanobot/agent/tools/fastcode.py`
- Pattern: Abstract class with `name`, `description`, `parameters` properties and async `execute()` method; registered in `ToolRegistry`

**Channel (nanobot):**
- Purpose: Adapter between a messaging platform and the nanobot message bus
- Examples: `nanobot/nanobot/channels/telegram.py`, `nanobot/nanobot/channels/slack.py`
- Pattern: Each channel converts platform-specific events to/from `InboundMessage`/`OutboundMessage` dataclasses

## Entry Points

**CLI (`main.py`):**
- Location: `main.py` (project root)
- Triggers: `python main.py query --query "..."` or `python main.py index ...`
- Responsibilities: Parses CLI args via Click, instantiates `FastCode`, calls `load_repository()` + `index_repository()` + `query()`

**Web Application (`web_app.py`):**
- Location: `web_app.py` (project root)
- Triggers: `uvicorn web_app:app --port 8001` (also the Docker entry point via `Dockerfile`)
- Responsibilities: Serves HTML frontend at `/`, exposes REST API at `/api/*`, initializes `FastCode` on startup, supports streaming responses via `StreamingResponse`

**REST API Only (`api.py`):**
- Location: `api.py` (project root)
- Triggers: `uvicorn api:app --port 8001`
- Responsibilities: Same API surface as `web_app.py` but without the HTML frontend; used when serving only the programmatic API

**Nanobot CLI (`nanobot/nanobot/cli/commands.py`):**
- Location: `nanobot/nanobot/cli/`
- Triggers: `nanobot gateway` command (Docker: `command: ["gateway"]`)
- Responsibilities: Starts channel adapters, message bus, agent loop, cron service

**Fastcode Module (`fastcode/__init__.py`):**
- Location: `fastcode/__init__.py`
- Triggers: `from fastcode import FastCode`
- Responsibilities: Public package API; exports `FastCode`, `RepositoryLoader`, `CodeParser`, `CodeIndexer`, `HybridRetriever`, `AnswerGenerator`, `IterativeAgent`, `AgentTools`

## Error Handling

**Strategy:** Try/except with logging at each pipeline stage; failures surface via HTTP 500 responses or CLI exit codes

**Patterns:**
- Component init failures are logged as warnings (e.g., resolver init in `fastcode/main.py` lines 226–232); pipeline continues with degraded accuracy
- `RepositoryLoader` raises exceptions on clone failure; caller handles via try/except
- FastAPI endpoints catch exceptions and raise `HTTPException` with descriptive messages
- LLM client initialization logs warnings for missing API keys but does not raise immediately; calls fail at request time
- Nanobot agent loop catches tool execution errors and returns error messages to the user

## Cross-Cutting Concerns

**Logging:** Python `logging` module throughout FastCode; `loguru` in Nanobot. FastCode logs to `./logs/fastcode.log` + console. Log level configurable in `config/config.yaml` under `logging.level`.

**Validation:** Pydantic models in `web_app.py` and `api.py` validate all HTTP request/response payloads. Nanobot uses Pydantic models in `nanobot/nanobot/config/schema.py`.

**Authentication:** No authentication on FastCode HTTP API (open by design for internal Docker network use). Nanobot channel adapters handle platform-specific auth (bot tokens, webhook secrets) via environment variables.

**Configuration:** Single YAML config file at `config/config.yaml` loaded by `FastCode.__init__()`. LLM credentials loaded from `.env` via `python-dotenv`. Nanobot uses `~/.nanobot/config.json` (mapped via Docker volume).

---

*Architecture analysis: 2026-02-24*
