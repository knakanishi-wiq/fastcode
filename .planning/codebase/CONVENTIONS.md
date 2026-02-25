# Coding Conventions

**Analysis Date:** 2026-02-24

## Naming Patterns

**Files:**
- `snake_case.py` for all Python modules (e.g., `answer_generator.py`, `vector_store.py`, `query_processor.py`)
- `camelCase.ts` for TypeScript bridge files (e.g., `server.ts`, `whatsapp.ts`)
- `UPPER_CASE.md` for documentation/skill files (e.g., `SKILL.md`, `COMMUNICATION.md`)

**Classes:**
- `PascalCase` for all classes: `CodeEmbedder`, `HybridRetriever`, `VectorStore`, `AnswerGenerator`, `BridgeServer`
- Abstract base classes suffixed with `Base` or implemented as ABC: `BaseChannel`, `LLMProvider`, `Tool`

**Functions/Methods:**
- `snake_case` for all Python functions: `embed_text()`, `index_repository()`, `generate_file_summary()`
- Private methods prefixed with underscore: `_load_model()`, `_add_file_level_element()`, `_initialize_client()`
- `camelCase` for TypeScript methods: `handleCommand()`, `broadcast()`, `sendMessage()`

**Variables:**
- `snake_case` for Python: `query_embedding`, `semantic_results`, `repo_filter`
- `camelCase` for TypeScript: `authDir`, `bridgeServer`

**Types/Dataclasses:**
- `PascalCase` for dataclasses and Pydantic models: `FunctionInfo`, `ClassInfo`, `CodeElement`, `ProcessedQuery`, `QueryRequest`, `StatusResponse`
- Optional fields use `Optional[T]` annotation consistently

**Constants:**
- `UPPER_SNAKE_CASE` for module-level constants: `MIN_SCORE_THRESHOLD = 0.15`

## Code Style

**Formatting:**
- `.editorconfig` present: UTF-8 charset, LF line endings, insert final newline, trim trailing whitespace
- No auto-formatter (no `.prettierrc` or `ruff format` config) in the main Python codebase
- `ruff` configured in `nanobot/pyproject.toml` with `line-length = 100`

**Linting (nanobot subpackage only):**
- Tool: `ruff` (configured in `nanobot/pyproject.toml`)
- Rules selected: `E` (pycodestyle), `F` (pyflakes), `I` (isort), `N` (naming), `W` (warnings)
- `E501` (line-too-long) is ignored — lines can exceed 100 chars in practice
- Main `fastcode/` package has no linter configuration

**Type Annotations:**
- Python 3.10+ union syntax used in nanobot: `str | None`, `list[dict[str, Any]] | None`
- Older `Optional[T]` syntax used throughout fastcode: `Optional[str]`, `Optional[List[str]]`
- Both styles coexist across the codebase

## Import Organization

**Order (Python):**
1. Standard library imports (`os`, `hashlib`, `logging`, `typing`, `dataclasses`)
2. Third-party packages (`numpy`, `faiss`, `openai`, `anthropic`, `loguru`)
3. Local relative imports (`from .utils import ...`, `from .embedder import ...`)

**Example from `fastcode/indexer.py`:**
```python
import hashlib
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from tqdm import tqdm

from .loader import RepositoryLoader
from .parser import CodeParser, FileParseResult
from .embedder import CodeEmbedder
```

**Path Aliases:**
- No path aliases used; relative imports within `fastcode/` package (e.g., `from .utils import`)
- nanobot uses full package paths: `from nanobot.bus.events import InboundMessage`

## Error Handling

**Patterns:**
- Input validation uses `raise ValueError` for bad inputs (e.g., `raise ValueError(f"Path does not exist: {path}")`)
- Initialization errors use `raise RuntimeError` (e.g., `raise RuntimeError("Vector store not initialized")`)
- Recoverable errors are caught, logged, and return graceful defaults:

```python
try:
    with open(overview_path, 'rb') as f:
        overviews = pickle.load(f)
except Exception as e:
    self.logger.error(f"Failed to load repository overviews: {e}")
    return {}
```

- Critical failures use `import traceback` + `self.logger.error(traceback.format_exc())` for full traces
- `HTTPException` used at API layer (`fastapi`) to bubble errors to callers
- nanobot uses broad `except Exception as e` with logging; never swallows silently

**Anti-patterns observed:**
- `import traceback` done inline inside except blocks (`fastcode/retriever.py`, `fastcode/main.py`) — not at top of file
- `print()` statements appear alongside `self.logger` calls in several retriever methods

## Logging

**Framework:**
- `fastcode/`: Python standard `logging` module — `self.logger = logging.getLogger(__name__)`
- `nanobot/`: `loguru` library — `from loguru import logger` (module-level singleton)

**Patterns:**
- Logger always named after module via `__name__`
- Log level usage: `logger.info()` for significant operations, `logger.debug()` for verbose tracing, `logger.warning()` for recoverable issues, `logger.error()` for failures
- f-strings used for all log messages: `self.logger.info(f"Indexed {len(self.elements)} code elements")`
- Checkpoint messages use checkmark emoji: `self.logger.info(f"✓ Successfully generated embeddings...")`
- Debug-level messages sometimes include `[DEBUG CLASSNAME]` prefix with emoji indicators (`❌`, `✓`)

## Comments

**When to Comment:**
- Inline comments explain non-obvious logic: `# Convert to 0-indexed`, `# HNSW index for fast approximate search`
- Section comments delimit multi-stage algorithms with decorative blocks:
```python
# ========================================
# STEP 1: Repository Selection
# ========================================
```
- `CRITICAL:`, `NOTE:`, `IMPORTANT:` prefixes mark high-importance comments
- Commented-out code left in place with explanatory comments (common in retriever logic)

**Docstrings:**
- Module-level: triple-quoted string at top of every Python file describing purpose
- Class-level: single-line docstring on every class
- Method-level: Google-style docstrings with `Args:` and `Returns:` sections:

```python
def embed_batch(self, texts: List[str]) -> np.ndarray:
    """
    Generate embeddings for a batch of texts

    Args:
        texts: List of input texts

    Returns:
        Array of embedding vectors
    """
```

- nanobot ABC methods include docstrings explaining the contract and expected behavior

## Function Design

**Size:** Some functions are very long (e.g., `retrieve()` in `fastcode/retriever.py` ~200 lines). Common in orchestration methods.

**Parameters:**
- Config dict pattern: classes receive `config: Dict[str, Any]` and extract sub-configs in `__init__`
- Optional parameters typed with `Optional[T] = None`
- Dependency injection for collaborators (loader, parser, embedder, vector_store passed into constructors)

**Return Values:**
- Functions returning collections default to empty list/dict on failure
- Boolean return for success/failure on IO operations: `def load(...) -> bool`
- `Optional[T]` return for functions that may find nothing

## Module Design

**Exports:**
- Each package has `__init__.py` with explicit `__all__` list: `fastcode/__init__.py` exports all public classes
- nanobot uses `__init__.py` for subpackage routing without `__all__`

**Barrel Files:**
- `fastcode/__init__.py` acts as barrel: imports all public classes from submodules
- nanobot subpackages have minimal `__init__.py` files (empty or single re-export)

**Dataclasses:**
- `@dataclass` used extensively for data models with `to_dict()` method pattern:
```python
@dataclass
class CodeElement:
    id: str
    type: str
    ...
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
```

**Pydantic Models:**
- Used exclusively at API boundary (`api.py`, `web_app.py`) for request/response validation
- `Field(...)` with `description=` used on all required fields

---

*Convention analysis: 2026-02-24*
