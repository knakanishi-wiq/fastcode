# Testing Patterns

**Analysis Date:** 2026-02-24

## Test Framework

**Runner:**
- `pytest` (listed in `requirements.txt` under `# Testing`)
- No `pytest.ini`, `setup.cfg`, or `pyproject.toml` found in the root `FastCode/` project — no pytest configuration for the main codebase
- nanobot subpackage has pytest configured in `nanobot/pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  asyncio_mode = "auto"
  testpaths = ["tests"]
  ```

**Assertion Library:**
- Standard `pytest` assertions (no separate assertion library)

**Async Support:**
- `pytest-asyncio` listed in `requirements.txt` and in nanobot's dev dependencies
- nanobot configured with `asyncio_mode = "auto"` — all async tests run automatically

**Run Commands:**
```bash
pytest                          # Run all tests
pytest --cov                    # Run with coverage (pytest-cov installed)
pytest -v                       # Verbose output
pytest tests/                   # Run tests in specific directory
```

## Test File Organization

**Current State:**
- **No test files exist in the main `FastCode/` codebase.** Despite `pytest`, `pytest-asyncio`, and `pytest-cov` being listed in `requirements.txt`, there are no `test_*.py` or `*_test.py` files anywhere in the repository.
- nanobot subpackage references `testpaths = ["tests"]` in its `pyproject.toml`, but no `tests/` directory exists under `nanobot/`.

**Intended Location (based on config):**
- nanobot: `nanobot/tests/` (configured but not present)
- main codebase: no convention established

**Naming (intended):**
- Files: `test_*.py` prefix (standard pytest discovery)
- Functions: `test_*` prefix

## Test Structure

**Suite Organization:**
No tests exist to analyze. Based on framework choice (`pytest`), the expected pattern would be:
```python
def test_embed_text():
    ...

class TestCodeEmbedder:
    def test_embed_batch(self):
        ...
```

**Patterns:**
- Setup pattern: Not established
- Teardown pattern: Not established
- Assertion pattern: Not established

## Mocking

**Framework:** `unittest.mock` (standard library) or `pytest-mock` — neither is listed as a dependency, indicating mocking strategy is not yet established.

**What to Mock (recommendations based on codebase structure):**
- LLM API calls: `openai.OpenAI`, `anthropic.Anthropic` — these make network calls
- File system operations: `open()`, `os.path.exists()` in `fastcode/vector_store.py` and `fastcode/loader.py`
- Embedding model: `SentenceTransformer` in `fastcode/embedder.py` — expensive GPU/CPU model load
- FAISS index: `faiss.read_index`, `faiss.write_index` in `fastcode/vector_store.py`

**What NOT to Mock:**
- Pure utility functions: `fastcode/utils.py` functions like `normalize_path()`, `get_language_from_extension()`, `clean_docstring()`
- Dataclass instantiation: `CodeElement`, `FunctionInfo`, `ClassInfo`, `ProcessedQuery`

## Fixtures and Factories

**Test Data:**
No fixtures exist. Based on the data models, factory patterns would look like:
```python
@pytest.fixture
def sample_code_element():
    return CodeElement(
        id="test_function_abc123",
        type="function",
        name="test_func",
        file_path="/repo/src/module.py",
        relative_path="src/module.py",
        language="python",
        start_line=1,
        end_line=10,
        code="def test_func(): pass",
        signature="def test_func()",
        docstring=None,
        summary="Test function",
        metadata={}
    )
```

**Location:**
- Not established; would go in `tests/conftest.py`

## Coverage

**Requirements:** None enforced (no `.coveragerc`, no `--cov` flags in any config)

**View Coverage:**
```bash
pytest --cov=fastcode --cov-report=html    # Generate HTML coverage report
pytest --cov=fastcode --cov-report=term    # Terminal report
```

## Test Types

**Unit Tests:**
- Not implemented. Key units that should be tested:
  - `fastcode/utils.py`: All pure utility functions (no external deps)
  - `fastcode/parser.py`: `CodeParser` parsing individual files
  - `fastcode/embedder.py`: `CodeEmbedder.embed_batch()`, `compute_similarity()`
  - `fastcode/vector_store.py`: `VectorStore.search()`, `add_vectors()`, filtering logic
  - `fastcode/retriever.py`: `_combine_results()`, `_rerank()`, `_diversify()`, `_apply_filters()`
  - `fastcode/indexer.py`: `_generate_id()`, `_generate_file_summary()`
  - `nanobot/nanobot/agent/tools/base.py`: `Tool.validate_params()`

**Integration Tests:**
- Not implemented. Key integrations that should be tested:
  - Full index → retrieve pipeline
  - API endpoints in `api.py` (FastAPI TestClient)
  - Channel message flow in nanobot

**E2E Tests:**
- Not implemented.

## Common Patterns

**Async Testing:**
Based on nanobot's `asyncio_mode = "auto"` config:
```python
# Tests just need to be async — no decorator needed
async def test_agent_loop():
    ...
```

**Error Testing:**
Expected pattern for testing `raise` conditions in `fastcode/loader.py`, `fastcode/vector_store.py`:
```python
import pytest

def test_vector_store_not_initialized_raises():
    store = VectorStore(config)
    with pytest.raises(RuntimeError, match="Vector store not initialized"):
        store.add_vectors(vectors, metadata)
```

## Key Gaps

The entire test suite is absent. High-priority areas to add tests:

1. **`fastcode/utils.py`** — Pure functions, no mocking needed, easy wins
2. **`fastcode/retriever.py` `_combine_results()`** — Core scoring logic with no I/O
3. **`fastcode/vector_store.py`** — In-memory mode (`in_memory=True`) enables testable storage without disk
4. **`api.py`** — FastAPI endpoints testable with `fastapi.testclient.TestClient`
5. **`nanobot/nanobot/agent/tools/base.py` `validate_params()`** — Pure validation logic

---

*Testing analysis: 2026-02-24*
