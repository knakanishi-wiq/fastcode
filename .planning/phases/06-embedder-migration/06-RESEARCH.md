# Phase 6: Embedder Migration - Research

**Researched:** 2026-02-25
**Domain:** litellm.embedding() with vertex_ai/gemini-embedding-001; sentence-transformers removal
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| R1 | CodeEmbedder.__init__() removes sentence-transformers/torch; uses litellm + embedding_dim from config | litellm.embedding() verified; no model download at init pattern confirmed |
| R2 | embed_batch() calls litellm.embedding(model, input=texts, task_type=task_type); extracts response.data[i]["embedding"]; L2-normalizes | Response structure verified in litellm source: data is list of Embedding objects with .embedding attribute or dict with "embedding" key |
| R3 | embed_text() adds task_type param (default "RETRIEVAL_QUERY"); delegates to embed_batch([text], task_type=task_type)[0] | Backwards-compatible; retriever.py callers pass no kwargs |
| R4 | embed_code_elements() passes task_type="RETRIEVAL_DOCUMENT" to embed_batch() | Single-line change; rest of method unchanged |
| R5 | indexer.py line 369: embed_text(overview_text, task_type="RETRIEVAL_DOCUMENT") | Confirmed at line 369; retriever.py embed_text calls pass no kwargs so default "RETRIEVAL_QUERY" is correct |
| R6 | embedding_dim read from config; no API call at init | Confirmed — litellm model is string identifier, no download needed |
| R7 | config.yaml embedding section updated: model, embedding_dim: 3072, remove device/max_seq_length | Config keys confirmed; current config verified |
</phase_requirements>

---

## Summary

Phase 6 replaces the local `SentenceTransformer` model in `fastcode/embedder.py` with `litellm.embedding()` pointing at `vertex_ai/gemini-embedding-001`. All changes are localized to three files: `embedder.py` (core rewrite), `config/config.yaml` (embedding section), and `indexer.py` (one line). The public API of `CodeEmbedder` (`embed_text`, `embed_batch`, `embed_code_elements`, `compute_similarity`, `compute_similarities`) is preserved with a backwards-compatible `task_type` parameter addition.

The litellm source code has been verified directly (installed version in environment). For `vertex_ai/` prefixed models, litellm routes to `VertexEmbedding.embedding()` which internally calls the Vertex AI text embeddings endpoint. The `task_type` kwarg passes through `**kwargs` into `optional_params` and maps directly to the Vertex `TextEmbeddingInput.task_type` field. The response structure is `response.data[i]["embedding"]` — each item in `data` is an `Embedding` object that supports dict-style access via `__getitem__`.

The `retriever.py` file has two `embed_text()` call sites (lines 415 and 734) — both pass no kwargs, so they will silently default to `task_type="RETRIEVAL_QUERY"` after the signature change, which is the correct behavior for query-time embedding. Only `indexer.py` line 369 (overview embedding, document-type) requires an explicit kwarg addition.

**Primary recommendation:** Rewrite `CodeEmbedder` in a single focused task: remove `_load_model()`; replace `embed_batch()` body with litellm call + response extraction + normalization loop; add `task_type` to `embed_text()` and `embed_batch()` signatures; update `embed_code_elements()` to pass `task_type="RETRIEVAL_DOCUMENT"`. Update config and indexer.py in the same commit.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| litellm[google] | >=1.80.8 (already in requirements.txt) | Calls vertex_ai/gemini-embedding-001 via ADC | Already used for all LLM calls in v1.0; unified API |
| numpy | (already present) | ndarray construction and L2 normalization | Already used throughout codebase |
| tqdm | (already present) | Progress bar for large batches (>100 texts) | Already used in indexer.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sentence-transformers | REMOVE | Old backend | Remove from requirements.txt (Phase 7) |
| torch | REMOVE (transitive) | Old hardware acceleration | Removed transitively when sentence-transformers removed (Phase 7) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| litellm.embedding() | google-cloud-aiplatform TextEmbeddingModel directly | litellm already in stack; consistent with LLM routing pattern |
| task_type as kwarg | input_type kwarg | litellm internally maps input_type to task_type (see transformation.py line 85); task_type is the Vertex-native name; use task_type |

**Installation:** No new packages — litellm[google] already present.

---

## Architecture Patterns

### Pattern 1: litellm.embedding() Call with task_type

**What:** Pass `task_type` as a direct kwarg to `litellm.embedding()`. litellm's `VertexAITextEmbeddingConfig.map_openai_params()` picks it up from `kwargs` and places it in `optional_params`, which then flows into each `TextEmbeddingInput` instance.

**When to use:** Every `embed_batch()` call.

**Example:**
```python
# Source: litellm source — vertex_embeddings/transformation.py verified in installed package
import litellm
import numpy as np
from tqdm import tqdm

def embed_batch(self, texts: List[str], task_type: str = "RETRIEVAL_QUERY") -> np.ndarray:
    if not texts:
        return np.array([])

    # Chunk into batches (litellm sends full input list to Vertex; chunking for progress + rate limiting)
    all_vectors = []
    batch_iter = range(0, len(texts), self.batch_size)
    if len(texts) > 100:
        batch_iter = tqdm(batch_iter, desc="Embedding")

    for i in batch_iter:
        batch = texts[i : i + self.batch_size]
        response = litellm.embedding(
            model=self.model_name,
            input=batch,
            task_type=task_type,
        )
        for item in response.data:
            all_vectors.append(item["embedding"])

    vectors = np.array(all_vectors, dtype=np.float32)

    if self.normalize:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)  # avoid div-by-zero
        vectors = vectors / norms

    return vectors
```

### Pattern 2: Response Vector Extraction

**What:** `response.data` is a list of `Embedding` objects. Each supports both dict-style access (`item["embedding"]`) and attribute access (`item.embedding`). The vector is a Python list of floats.

**Verified in:** litellm installed source — `litellm/types/utils.py` `Embedding` class has `__getitem__` delegating to `getattr`. `litellm/llms/vertex_ai/vertex_embeddings/transformation.py` line 237: `"embedding": embedding["values"]` — so the final `.data[i]["embedding"]` value is the raw list of floats from Vertex predictions.

```python
# Extraction pattern — both styles work; use dict-style for consistency with OpenAI SDK patterns
vectors = [item["embedding"] for item in response.data]
# OR attribute style:
vectors = [item.embedding for item in response.data]
```

### Pattern 3: CodeEmbedder.__init__() After Migration

**What:** Remove all sentence-transformers references. Read `embedding_dim` from config (no runtime detection call).

```python
import litellm
# No torch, no sentence_transformers, no platform

class CodeEmbedder:
    def __init__(self, config):
        self.config = config
        self.embedding_config = config.get("embedding", {})
        self.logger = logging.getLogger(__name__)

        self.model_name = self.embedding_config.get("model", "vertex_ai/gemini-embedding-001")
        self.batch_size = self.embedding_config.get("batch_size", 32)
        self.normalize = self.embedding_config.get("normalize_embeddings", True)
        self.embedding_dim = self.embedding_config.get("embedding_dim", 3072)

        self.logger.info(f"Embedding model: {self.model_name} (dim={self.embedding_dim})")
        # No self.model = _load_model() — no download at init
```

### Pattern 4: embed_text() Signature Change

**What:** Add `task_type` with default `"RETRIEVAL_QUERY"`. Pass through to `embed_batch()`.

```python
def embed_text(self, text: str, task_type: str = "RETRIEVAL_QUERY") -> np.ndarray:
    return self.embed_batch([text], task_type=task_type)[0]
```

**Backwards compatibility:** All existing `retriever.py` callers (`embed_text(query)`, `embed_text(semantic_query_text)`) pass no kwargs — they receive `"RETRIEVAL_QUERY"` by default, which is correct for search queries.

### Pattern 5: indexer.py Change (Line 369)

**What:** Single-line kwarg addition. No other changes.

```python
# Before (line 369):
embedding = self.embedder.embed_text(overview_text)

# After:
embedding = self.embedder.embed_text(overview_text, task_type="RETRIEVAL_DOCUMENT")
```

### Pattern 6: config.yaml Embedding Section

```yaml
# After migration:
embedding:
  model: "vertex_ai/gemini-embedding-001"
  embedding_dim: 3072          # gemini-embedding-001 default; 768 or 1536 also valid
  batch_size: 32               # Outer chunk size; litellm sends each chunk as one API call
  normalize_embeddings: true   # L2-normalize for FAISS cosine similarity
  # Removed: device, max_seq_length (server-side model)
```

### Anti-Patterns to Avoid

- **Calling litellm.embedding() with one text at a time in a Python loop:** Vertex AI's `batchEmbedContents` endpoint accepts a list; send `batch_size` items per call. The existing `batch_size: 32` config is the right outer chunk size.
- **Detecting embedding_dim at init via an API call:** Read from config. The REQUIREMENTS.md explicitly forbids this (R6). FAISS `IndexHNSWFlat` is constructed with this value.
- **Using `input_type` kwarg instead of `task_type`:** litellm's `map_openai_params` maps `input_type` → `task_type`, but `task_type` is the canonical Vertex name and is what the config doc uses.
- **Keeping `platform` import:** The `platform.system() == 'Darwin'` pool=None workaround was sentence-transformers-specific. Remove entirely.
- **Forgetting to handle zero-norm vectors in L2 normalization:** Use `np.where(norms == 0, 1.0, norms)` to avoid divide-by-zero on degenerate inputs.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vertex AI auth + token refresh | Custom auth wrapper | litellm with ADC | Already handles VERTEXAI_PROJECT/LOCATION env vars; token refresh automatic |
| Batch size enforcement by Vertex API | Custom retry/split logic | litellm + outer chunking loop | litellm sends the full batch to Vertex; outer loop is for progress bar + rate limiting, not API enforcement |
| HTTP retry on rate limits | Custom exponential backoff | litellm built-in retry (litellm.num_retries) | Already configured; follow same pattern as LLM calls |

**Key insight:** litellm handles the Vertex API protocol, auth, and response normalization. The embedder just needs to call it and unpack `response.data`.

---

## Common Pitfalls

### Pitfall 1: task_type Not Forwarded to API

**What goes wrong:** `task_type` kwarg is passed to `litellm.embedding()` but silently dropped, returning generic embeddings without task optimization.

**Why it happens:** litellm's `VertexAITextEmbeddingConfig.map_openai_params()` only picks `task_type` from `kwargs` (not `non_default_params`). This was verified in the transformation source. If the litellm version installed is older than when `task_type` was added, it may not be recognized.

**How to avoid:** Verify with the smoke test (R11 in Phase 7): a successful call returning shape `(3072,)` confirms routing is correct. The task_type value doesn't affect the output dimension — only embedding quality for retrieval.

**Warning signs:** No exception is raised — wrong behavior is silent. Would only surface as degraded retrieval quality.

### Pitfall 2: response.data Item Access

**What goes wrong:** Accessing `response.data[i].embedding` (attribute) instead of `response.data[i]["embedding"]` (dict), or vice versa, causes AttributeError or KeyError.

**Why it happens:** litellm's `Embedding` class supports both via custom `__getitem__` and `__getattr__`. Both work, but dict-style is consistent with OpenAI SDK patterns and safer if litellm changes the class internals.

**How to avoid:** Use `item["embedding"]` consistently. This matches the pattern seen in litellm's own transformation code.

**Warning signs:** `KeyError: 'embedding'` or `AttributeError: 'Embedding' object has no attribute 'embedding'`.

### Pitfall 3: Stale FAISS Index After Dimension Change

**What goes wrong:** Existing `.index` files in `./data/vector_store/` were built with 384-dim (all-MiniLM) vectors. Loading them after migration causes a dimension mismatch crash.

**Why it happens:** FAISS `IndexHNSWFlat` is initialized with a fixed dimension. Loading a 384-dim index then querying with a 3072-dim vector fails.

**How to avoid:** Delete `./data/vector_store/` before first run after migration. Document this prominently. This is a known consequence in REQUIREMENTS.md — no code change needed, just documentation.

**Warning signs:** `faiss.swigfaiss.Error: d (3072) != d (384)` on startup or first search.

### Pitfall 4: embed_batch() Returns Wrong Shape

**What goes wrong:** `embed_batch([])` edge case, or single-text calls return wrong shape.

**Why it happens:** `np.array([item["embedding"] for item in response.data])` — if `response.data` is empty, this creates a 0-dim array. If a single text, shape is `(1, 3072)` which is correct for `embed_batch`; `embed_text` then takes `[0]` to get shape `(3072,)`.

**How to avoid:** Keep the `if not texts: return np.array([])` guard. Preserve the delegate pattern `embed_text → embed_batch([text])[0]`.

**Warning signs:** `IndexError` when calling `embed_text()` after `embed_batch()` returns unexpected shape.

### Pitfall 5: platform Import Left Behind

**What goes wrong:** `import platform` remains in embedder.py with the `platform.system() == 'Darwin'` code removed, causing a linter warning (or if the code block is left, a NameError for undefined `pool` parameter).

**How to avoid:** Remove `import platform` and the entire `if platform.system() == 'Darwin': encode_kwargs['pool'] = None` block.

---

## Code Examples

Verified patterns from installed litellm source:

### Full embed_batch() Implementation

```python
# Source: verified against litellm installed source (vertex_embeddings/transformation.py)
import litellm
import numpy as np
from tqdm import tqdm
from typing import List

def embed_batch(self, texts: List[str], task_type: str = "RETRIEVAL_QUERY") -> np.ndarray:
    """Generate embeddings for a batch of texts via litellm/VertexAI."""
    if not texts:
        return np.array([])

    all_vectors: List[List[float]] = []
    chunk_indices = range(0, len(texts), self.batch_size)

    if len(texts) > 100:
        chunk_indices = tqdm(chunk_indices, desc="Generating embeddings")

    for i in chunk_indices:
        batch = texts[i : i + self.batch_size]
        response = litellm.embedding(
            model=self.model_name,
            input=batch,
            task_type=task_type,
        )
        for item in response.data:
            all_vectors.append(item["embedding"])

    vectors = np.array(all_vectors, dtype=np.float32)

    if self.normalize and len(vectors) > 0:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        vectors = vectors / norms

    return vectors
```

### embed_text() With task_type

```python
def embed_text(self, text: str, task_type: str = "RETRIEVAL_QUERY") -> np.ndarray:
    """Generate embedding for a single text."""
    return self.embed_batch([text], task_type=task_type)[0]
```

### embed_code_elements() One-Line Change

```python
# Only change in embed_code_elements(): add task_type kwarg
embeddings = self.embed_batch(texts, task_type="RETRIEVAL_DOCUMENT")
```

### Smoke Test Pattern (for Phase 7 — follows v1.0 pattern in test_vertexai_smoke.py)

```python
# Source: modeled on tests/test_vertexai_smoke.py (existing pattern)
import os
import pytest
import numpy as np
from dotenv import load_dotenv
from fastcode.embedder import CodeEmbedder

load_dotenv()

class TestEmbedderSmoke:
    @pytest.mark.skipif(
        not os.environ.get("VERTEXAI_PROJECT"),
        reason="VERTEXAI_PROJECT not set — skipping live test",
    )
    def test_embed_text_returns_correct_shape_and_normalized(self):
        config = {"embedding": {"model": "vertex_ai/gemini-embedding-001", "embedding_dim": 3072, "batch_size": 32, "normalize_embeddings": True}}
        embedder = CodeEmbedder(config)
        result = embedder.embed_text("hello world", task_type="RETRIEVAL_QUERY")
        assert isinstance(result, np.ndarray)
        assert result.shape == (3072,)
        assert np.all(np.isfinite(result))
        assert abs(np.linalg.norm(result) - 1.0) < 1e-5
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SentenceTransformer local model download | litellm.embedding() → VertexAI API | Phase 6 (v1.1) | No model download at init; no device management; no torch dependency |
| 384-dim (all-MiniLM) | 3072-dim (gemini-embedding-001) | Phase 6 (v1.1) | Better embedding quality; all existing FAISS indexes must be deleted |
| device auto-detection (CUDA/MPS/CPU) | Server-side computation | Phase 6 (v1.1) | Remove device config; remove platform workaround |

**Deprecated/outdated:**
- `device` config key: server-side model, not applicable
- `max_seq_length` config key: handled server-side; Vertex truncates automatically
- `_load_model()` method: remove entirely
- `sentence-transformers` + `torch` imports: remove from embedder.py (package removal in Phase 7)
- `platform` import: workaround for macOS sentence-transformers multiprocessing bug — not needed

---

## Key Findings: Answer to Research Questions

### Q1: Exact litellm.embedding() call signature for vertex_ai/gemini-embedding-001 with task_type?

```python
litellm.embedding(
    model="vertex_ai/gemini-embedding-001",
    input=["text1", "text2"],  # list of strings
    task_type="RETRIEVAL_DOCUMENT",  # or "RETRIEVAL_QUERY"
)
```

`task_type` is a Vertex-specific kwarg captured by `**kwargs` in `litellm.embedding()` and routed through `VertexAITextEmbeddingConfig.map_openai_params()` into `optional_params["task_type"]`.

**Confidence: HIGH** — verified in installed litellm source `vertex_embeddings/transformation.py`.

### Q2: Response structure — how to extract the vector?

```python
response.data[i]["embedding"]  # list of floats
```

`response.data` is a `List[Embedding]`. Each `Embedding` supports dict-style access. The vector is a Python `list[float]` — convert to ndarray with `np.array(...)`.

**Confidence: HIGH** — verified in litellm source `types/utils.py` (`Embedding.__getitem__`) and `vertex_embeddings/transformation.py` (line 237: `"embedding": embedding["values"]`).

### Q3: Does litellm handle batches for gemini-embedding-001, or per-item calls?

litellm sends the full `input` list in one Vertex API call (using `batchEmbedContents` or the `instances` array endpoint depending on model routing). For `vertex_ai/gemini-embedding-001`, it routes to `VertexEmbedding.embedding()` which sends all items in one HTTP request.

**Recommendation:** Chunk externally with `batch_size: 32` from config as the outer loop — this provides progress reporting and guards against rate limiting. Each chunk = one API call.

**Confidence: HIGH** — verified in litellm `main.py` (lines 5130-5185) and `vertex_embeddings/embedding_handler.py`.

### Q4: How does tqdm progress bar translate from sentence-transformers?

Old: `show_progress_bar=True` kwarg to `SentenceTransformer.encode()`.
New: Wrap the chunk index range with `tqdm(range(0, len(texts), self.batch_size), desc="Generating embeddings")` when `len(texts) > 100`.

```python
chunk_indices = range(0, len(texts), self.batch_size)
if len(texts) > 100:
    chunk_indices = tqdm(chunk_indices, desc="Generating embeddings")
```

**Confidence: HIGH** — tqdm already in requirements.txt; already imported in indexer.py.

### Q5: Where exactly in indexer.py is the overview embed_text() call?

**Line 369** of `fastcode/indexer.py`:
```python
embedding = self.embedder.embed_text(overview_text)
```
Inside `_save_repository_overview()`. This is the only `embed_text()` call in indexer.py. Change to:
```python
embedding = self.embedder.embed_text(overview_text, task_type="RETRIEVAL_DOCUMENT")
```

**Confidence: HIGH** — confirmed by reading the file.

### Q6: Which retriever.py call sites call embed_text() / embed_batch() — do they pass any kwargs?

Two `embed_text()` call sites in `fastcode/retriever.py`:
- **Line 415:** `query_embedding = self.embedder.embed_text(semantic_query_text)` — no kwargs
- **Line 734:** `query_embedding = self.embedder.embed_text(query)` — no kwargs

Both are query-time embeddings. Default `task_type="RETRIEVAL_QUERY"` is correct. **Zero changes required in retriever.py.**

No `embed_batch()` calls in retriever.py.

**Confidence: HIGH** — confirmed by grep.

### Q7: Any other files that import or instantiate CodeEmbedder?

Files that import `CodeEmbedder`:
- `fastcode/embedder.py` — definition
- `fastcode/indexer.py` — type annotation in `__init__` signature
- `fastcode/retriever.py` — type annotation in `__init__` signature
- `fastcode/main.py` — instantiation at line 83: `self.embedder = CodeEmbedder(self.config)`

**main.py** also has `"sentence-transformers/all-MiniLM-L6-v2"` hardcoded at line 848 as a default model string in some config fallback. This is in scope for R10 (Phase 7), not Phase 6.

**Confidence: HIGH** — confirmed by grep across all .py files.

---

## Open Questions

1. **gemini-embedding-001 batch size limit**
   - What we know: Vertex AI documentation mentions `batchEmbedContents` API; litellm sends full input list in one HTTP request
   - What's unclear: Whether Vertex enforces a hard per-request item limit (e.g., max 250 items per batchEmbedContents call)
   - Recommendation: Keep `batch_size: 32` as the outer chunk size. If Vertex enforces a limit, litellm's retry or HTTP error will surface it clearly. 32 is well within any reasonable limit.

2. **task_type kwarg routing in very old litellm versions**
   - What we know: Verified in installed version (>=1.80.8 per requirements.txt); `task_type` is picked from `kwargs` in `map_openai_params`
   - What's unclear: Exact version when `task_type` was added as a recognized kwarg
   - Recommendation: The version constraint `>=1.80.8` in requirements.txt covers current usage. No action needed.

---

## Sources

### Primary (HIGH confidence)
- Installed litellm source: `/Users/knakanishi/Library/Python/3.13/lib/python/site-packages/litellm/llms/vertex_ai/vertex_embeddings/transformation.py` — verified task_type routing, response structure
- Installed litellm source: `/Users/knakanishi/Library/Python/3.13/lib/python/site-packages/litellm/types/utils.py` — verified EmbeddingResponse and Embedding type structure
- Installed litellm source: `/Users/knakanishi/Library/Python/3.13/lib/python/site-packages/litellm/main.py` (lines 5130-5185) — verified vertex_ai embedding routing
- `fastcode/embedder.py` — read directly; confirmed current implementation
- `fastcode/indexer.py` — read directly; confirmed line 369 call site
- `fastcode/retriever.py` — grepped; confirmed two embed_text() call sites with no kwargs
- `fastcode/main.py` — grepped; confirmed CodeEmbedder instantiation and default model string at line 848

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` — full requirement specifications R1–R11 read directly

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — litellm already in use; source verified locally
- Architecture: HIGH — all call sites confirmed by reading/grepping source files
- Pitfalls: HIGH — based on verified source code, not speculation

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (litellm embedding API is stable; Vertex AI model names stable)
