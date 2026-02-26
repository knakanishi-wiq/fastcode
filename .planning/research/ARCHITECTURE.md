# Architecture Research

**Domain:** Embedding backend migration — sentence-transformers to litellm.embedding() + VertexAI
**Researched:** 2026-02-25
**Confidence:** HIGH (codebase analysis + litellm official docs + VertexAI official docs)

---

## Standard Architecture

### System Overview

```
config/config.yaml (embedding: section)
       |
       v
fastcode/embedder.py  ←  REWRITE: CodeEmbedder
  - embed_text(text, task_type)         ← task_type param added
  - embed_batch(texts, task_type)       ← task_type param added
  - embed_code_elements(elements)       ← calls embed_batch with RETRIEVAL_DOCUMENT
  - embedding_dim: int                  ← hardcoded from config, not from model
       |
       |---------- called by ----------+
       |                               |
       v                               v
fastcode/indexer.py              fastcode/retriever.py
  embed_code_elements(elements)    embed_text(query)          ← RETRIEVAL_QUERY
  embed_text(overview_text)        (in _semantic_search,
  (RETRIEVAL_DOCUMENT both)         _select_relevant_repositories)
       |                               |
       v                               v
fastcode/vector_store.py         fastcode/vector_store.py
  initialize(embedding_dim)         search(query_vector)
  add_vectors(vectors, metadata)
```

### Component Responsibilities

| Component | Responsibility | Change Type |
|-----------|----------------|-------------|
| `fastcode/embedder.py` | All embedding calls; owns `embedding_dim` | REWRITE |
| `fastcode/indexer.py` | Calls `embed_code_elements` (document) and `embed_text` (overview) | ADD `task_type` awareness |
| `fastcode/retriever.py` | Calls `embed_text` (query) at 2 sites | ADD `task_type` awareness |
| `fastcode/vector_store.py` | Receives `embedding_dim` from embedder; FAISS ops | NO CHANGE |
| `fastcode/main.py` | Passes `self.embedder.embedding_dim` to `vector_store.initialize()` at 4 sites | NO CHANGE (dim source changes inside embedder) |
| `config/config.yaml` | `embedding:` section fields | MODIFY — replace sentence-transformer fields |
| `requirements.txt` | Remove sentence-transformers, torch | MODIFY |

---

## Recommended Project Structure

No new files needed. This is a replacement rewrite of one module:

```
fastcode/
├── embedder.py          # REWRITE — CodeEmbedder backed by litellm.embedding()
├── indexer.py           # TOUCH — pass task_type="RETRIEVAL_DOCUMENT" to embed calls
├── retriever.py         # TOUCH — pass task_type="RETRIEVAL_QUERY" to embed_text calls
├── vector_store.py      # NO CHANGE — dimension-agnostic
├── main.py              # NO CHANGE — reads self.embedder.embedding_dim as before
└── llm_client.py        # NO CHANGE — LLM calls only, not embedding
config/
└── config.yaml          # MODIFY embedding: section
tests/
└── test_embedding_smoke.py   # NEW — ADC smoke test parallel to existing LLM smoke test
```

### Structure Rationale

- **No new module for embedding client:** litellm.embedding() is a top-level function, same as litellm.completion(). The existing CodeEmbedder class boundary is preserved — callers (indexer, retriever, main) see no interface change.
- **No embedding_client.py:** Unlike the LLM migration which centralized 5 disparate call sites, embedding has exactly one call site (CodeEmbedder). A separate module would add indirection with no benefit.

---

## Architectural Patterns

### Pattern 1: Static `embedding_dim` from Config (replaces `get_sentence_embedding_dimension()`)

**What:** The new CodeEmbedder reads `embedding_dim` from `config["embedding"]["dimension"]` instead of querying it from the model object. The value is set in config.yaml.

**When to use:** Always, for any API-backed embedding model where dimension is determined by the API call's `output_dimensionality` parameter rather than the model's intrinsic shape.

**Why:** sentence-transformers returned dimension via `model.get_sentence_embedding_dimension()` because the local model object knows its own shape. litellm.embedding() makes a network call — there is no model object to query. Dimension is known from the model's documentation (gemini-embedding-001 default: 3072; with `output_dimensionality=768`: 768).

**Trade-offs:**
- Pro: No "probe embedding" call required at startup (avoids extra API round-trip)
- Pro: Dimension is explicit in config, visible at a glance
- Con: Config and actual output must be kept in sync; misconfiguration causes silent dimension mismatch at FAISS initialization

**Example:**
```python
# config/config.yaml
embedding:
  model: "vertex_ai/gemini-embedding-001"
  dimension: 768              # must match output_dimensionality below
  output_dimensionality: 768  # passed to litellm.embedding()

# fastcode/embedder.py
class CodeEmbedder:
    def __init__(self, config):
        self.embedding_config = config.get("embedding", {})
        self.model_name = self.embedding_config.get("model", "vertex_ai/gemini-embedding-001")
        self.output_dimensionality = self.embedding_config.get("output_dimensionality", 768)
        # Static from config — no API call at init time
        self.embedding_dim = self.embedding_config.get("dimension", 768)
```

### Pattern 2: `task_type` as Parameter on `embed_text` and `embed_batch`

**What:** Add `task_type: str = "RETRIEVAL_DOCUMENT"` parameter to `embed_text()` and `embed_batch()`. Indexing callers pass `RETRIEVAL_DOCUMENT`; query callers pass `RETRIEVAL_QUERY`.

**When to use:** When the embedding model uses task-differentiated representations (gemini-embedding-001's `RETRIEVAL_DOCUMENT` vs `RETRIEVAL_QUERY` produce meaningfully different vectors optimized for each role).

**Trade-offs:**
- Pro: Correct semantic alignment — documents and queries are encoded for their respective roles
- Pro: Interface is explicit and self-documenting at the call site
- Con: One additional parameter to thread through the call chain
- Con: If `task_type` is accidentally omitted, the default falls back to `RETRIEVAL_DOCUMENT`; callers must be explicit

**Example:**
```python
# fastcode/embedder.py
def embed_text(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
    return self.embed_batch([text], task_type=task_type)[0]

def embed_batch(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
    # litellm.embedding() accepts task_type as a Vertex-specific kwarg
    response = litellm.embedding(
        model=self.model_name,
        input=texts,
        task_type=task_type,
        dimensions=self.output_dimensionality,
    )
    vectors = np.array([item["embedding"] for item in response.data], dtype=np.float32)
    return vectors

# fastcode/retriever.py — query embedding
query_embedding = self.embedder.embed_text(query, task_type="RETRIEVAL_QUERY")

# fastcode/indexer.py — document embedding (index time)
embedding = self.embedder.embed_text(overview_text, task_type="RETRIEVAL_DOCUMENT")
elements_with_embeddings = self.embedder.embed_code_elements(element_dicts)  # internally uses RETRIEVAL_DOCUMENT
```

### Pattern 3: One-Input-Per-Request Batching for gemini-embedding-001

**What:** gemini-embedding-001 accepts only a single input text per API request (confirmed by official Vertex AI docs). Batch embedding requires looping N requests.

**When to use:** Always for gemini-embedding-001. Other Vertex AI embedding models (text-embedding-004) accept up to 250 inputs.

**Trade-offs:**
- Con: Significant throughput reduction at index time — N documents = N API calls instead of ceil(N/250) calls
- Pro: Simple implementation, no chunking logic needed
- Mitigation: Indexing is a one-time offline operation; latency matters less than correctness

**Example:**
```python
def embed_batch(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
    if not texts:
        return np.array([])
    embeddings = []
    for text in texts:
        response = litellm.embedding(
            model=self.model_name,
            input=[text],          # single item — gemini-embedding-001 limit
            task_type=task_type,
            dimensions=self.output_dimensionality,
        )
        embeddings.append(response.data[0]["embedding"])
    return np.array(embeddings, dtype=np.float32)
```

**Alternative:** If litellm's Python SDK performs SDK-level batching transparently (unconfirmed), pass all texts at once and verify behavior. Fall back to the loop if a batch returns errors.

### Pattern 4: Response Vector Extraction

**What:** litellm.embedding() returns an OpenAI-compatible response object. The embedding vector lives at `response.data[0]["embedding"]` (a Python list of floats).

**Example:**
```python
response = litellm.embedding(
    model="vertex_ai/gemini-embedding-001",
    input=["some text"],
    task_type="RETRIEVAL_DOCUMENT",
    dimensions=768,
)
# Response structure:
# response.data = [{"object": "embedding", "index": 0, "embedding": [float, ...]}]
vector = np.array(response.data[0]["embedding"], dtype=np.float32)
```

---

## Data Flow

### Index-Time Embedding Flow

```
CodeIndexer.index_repository()
  → embedder.embed_code_elements(element_dicts)
      → embed_batch(texts, task_type="RETRIEVAL_DOCUMENT")
          → for each text:
              litellm.embedding(model, input=[text], task_type="RETRIEVAL_DOCUMENT", dimensions=768)
          → np.array([vectors])   shape: (N, 768)
  → elements[i].metadata["embedding"] = vector

CodeIndexer._save_repository_overview()
  → embedder.embed_text(overview_text, task_type="RETRIEVAL_DOCUMENT")
      → embed_batch([overview_text], task_type="RETRIEVAL_DOCUMENT")
          → litellm.embedding(model, input=[overview_text], task_type="RETRIEVAL_DOCUMENT", dimensions=768)
      → vector   shape: (768,)
  → vector_store.save_repo_overview(embedding=vector)
```

### Query-Time Embedding Flow

```
HybridRetriever._semantic_search(query)
  → embedder.embed_text(query, task_type="RETRIEVAL_QUERY")
      → litellm.embedding(model, input=[query], task_type="RETRIEVAL_QUERY", dimensions=768)
      → vector   shape: (768,)
  → vector_store.search(query_vector=vector)

HybridRetriever._select_relevant_repositories(query)
  → embedder.embed_text(query, task_type="RETRIEVAL_QUERY")   ← same pattern
  → vector_store.search_repository_overviews(query_embedding=vector)
```

### FAISS Initialization Flow

```
main.py: FastCode.__init__()
  → self.embedder = CodeEmbedder(config)
      → self.embedding_dim = config["embedding"]["dimension"]   # 768, from config.yaml
      [NO API call at init time]
  → self.vector_store = VectorStore(config)

main.py: FastCode._index_repository()
  → if self.vector_store.dimension is None:
        self.vector_store.initialize(self.embedder.embedding_dim)   # initialize(768)
        [FAISS IndexHNSWFlat(768, m, METRIC_INNER_PRODUCT)]

retriever.py: HybridRetriever.reload_specific_repositories()
  → if self.filtered_vector_store is None:
        self.filtered_vector_store = VectorStore(config)
        self.filtered_vector_store.initialize(self.embedder.embedding_dim)  # initialize(768)
```

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| VertexAI gemini-embedding-001 | `litellm.embedding(model="vertex_ai/gemini-embedding-001", ...)` | ADC auth; VERTEXAI_PROJECT + VERTEXAI_LOCATION env vars required (same as LLM calls) |
| FAISS | `VectorStore.initialize(dim)` — no change | Receives 768 instead of 384; existing index files must be deleted on first v1.1 run |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `embedder.py` → litellm | `litellm.embedding()` direct call | No wrapper module needed — single call site |
| `indexer.py` → `embedder.py` | `embed_code_elements(elements)` — no signature change | Internally calls `embed_batch(..., task_type="RETRIEVAL_DOCUMENT")` |
| `indexer.py` → `embedder.py` | `embed_text(text, task_type="RETRIEVAL_DOCUMENT")` — new param at call site | indexer explicitly passes task_type |
| `retriever.py` → `embedder.py` | `embed_text(text, task_type="RETRIEVAL_QUERY")` — new param at call site | retriever explicitly passes task_type |
| `main.py` → `embedder.py` | `self.embedder.embedding_dim` — no change | Source of truth changes (config not model.get_sentence_embedding_dimension()); callers unchanged |
| `vector_store.py` | `initialize(dimension)` — no change | Dimension value changes from 384 to 768; API unchanged |

---

## Config Changes

### config.yaml — `embedding:` section

```yaml
# BEFORE (sentence-transformers)
embedding:
  model: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
  device: "auto"
  batch_size: 32
  max_seq_length: 512
  normalize_embeddings: true

# AFTER (litellm + VertexAI)
embedding:
  model: "vertex_ai/gemini-embedding-001"
  dimension: 768               # must match output_dimensionality
  output_dimensionality: 768   # 768 | 1536 | 3072 (default 3072 if omitted)
  # device, batch_size, max_seq_length, normalize_embeddings — REMOVE (not applicable)
```

**Why 768 not 3072:** The PROJECT.md constraint states "FAISS index reindex required: embedding dimension changes (384 → 768)". 768 balances quality vs storage. Google's normalization note: 3072-dim embeddings are pre-normalized; 768-dim embeddings must be normalized manually (FAISS `normalize_L2` handles this already in `vector_store.add_vectors`).

---

## Files: New vs Modified vs Unchanged

| File | Status | What Changes |
|------|--------|--------------|
| `fastcode/embedder.py` | REWRITE | Remove SentenceTransformer; replace with litellm.embedding(); add task_type param; change embedding_dim source |
| `fastcode/indexer.py` | MODIFY (minimal) | Add `task_type="RETRIEVAL_DOCUMENT"` to `embed_text()` call at line 369 |
| `fastcode/retriever.py` | MODIFY (minimal) | Add `task_type="RETRIEVAL_QUERY"` to `embed_text()` calls at lines 415 and 734 |
| `fastcode/vector_store.py` | NO CHANGE | Dimension-agnostic |
| `fastcode/main.py` | NO CHANGE | Reads `self.embedder.embedding_dim` — source changes internally |
| `fastcode/llm_client.py` | NO CHANGE | LLM calls only |
| `config/config.yaml` | MODIFY | Replace embedding: section fields |
| `requirements.txt` | MODIFY | Remove sentence-transformers, torch; litellm already present |
| `tests/test_embedding_smoke.py` | CREATE | ADC smoke test for embedding |

---

## Build Order

Dependencies dictate this order:

**Step 1 — Rewrite `fastcode/embedder.py`**
Pure replacement. No callers change until Step 2 and 3. Can be tested in isolation by constructing CodeEmbedder directly.

**Step 2 — Touch `fastcode/indexer.py`** (2 sites)
Add `task_type="RETRIEVAL_DOCUMENT"` at:
- Line 369: `self.embedder.embed_text(overview_text)` → `self.embedder.embed_text(overview_text, task_type="RETRIEVAL_DOCUMENT")`
- `embed_code_elements` requires no change — task_type is baked inside the method

**Step 3 — Touch `fastcode/retriever.py`** (2 sites)
Add `task_type="RETRIEVAL_QUERY"` at:
- Line 415: `self.embedder.embed_text(semantic_query_text)` → `self.embedder.embed_text(semantic_query_text, task_type="RETRIEVAL_QUERY")`
- Line 734: `self.embedder.embed_text(query)` → `self.embedder.embed_text(query, task_type="RETRIEVAL_QUERY")`

**Step 4 — Update `config/config.yaml`**
Replace the `embedding:` section. Remove `device`, `batch_size`, `max_seq_length`, `normalize_embeddings`. Add `dimension` and `output_dimensionality`.

**Step 5 — Update `requirements.txt`**
Remove `sentence-transformers`, `torch`. Confirm `litellm` is present (already used for LLM calls).

**Step 6 — Write `tests/test_embedding_smoke.py`**
Call `embedder.embed_text("hello world", task_type="RETRIEVAL_QUERY")` via ADC. Assert vector shape is `(768,)`. Skip if `VERTEXAI_PROJECT` not set (same pattern as LLM smoke test).

**Step 7 — Delete existing FAISS indexes**
Dimension change (384 → 768) makes old indexes incompatible. Document this in migration notes: clear `./data/vector_store/*.faiss` and `*.pkl` before first run.

---

## Anti-Patterns

### Anti-Pattern 1: Probing Dimension via a Real API Call at Init

**What people do:** Call `litellm.embedding()` with a test string during `CodeEmbedder.__init__()`, then read `len(response.data[0]["embedding"])` to set `self.embedding_dim`.

**Why it's wrong:** Adds a real API round-trip (and cost) every time the application starts, including during tests and CI. Also fails fast if credentials are missing at startup rather than at actual use time.

**Do this instead:** Read `dimension` from `config["embedding"]["dimension"]`. Hardcode the known value in config.yaml. Verify alignment in the smoke test.

### Anti-Pattern 2: Using Default task_type (No Parameter)

**What people do:** Call `litellm.embedding(model=..., input=[text])` without `task_type`, relying on the default.

**Why it's wrong:** The VertexAI default for `task_type` is `RETRIEVAL_QUERY`. Documents indexed without `RETRIEVAL_DOCUMENT` are semantically misaligned — the model encodes them as if they were queries. Similarity scores between documents and queries will be lower quality.

**Do this instead:** Always pass `task_type` explicitly. Use `"RETRIEVAL_DOCUMENT"` for all indexing calls; use `"RETRIEVAL_QUERY"` for all query embedding calls.

### Anti-Pattern 3: Keeping `embed_code_elements` as the Only Task-Type Entry Point

**What people do:** Only add `task_type` to `embed_code_elements()` (which handles bulk indexing) but not to `embed_text()` (which handles overview indexing in `indexer.py` and all query embeddings in `retriever.py`).

**Why it's wrong:** `indexer._save_repository_overview()` calls `embed_text()` directly, not `embed_code_elements()`. `retriever.py` also calls `embed_text()` directly. All three paths need task_type.

**Do this instead:** Add `task_type` parameter to both `embed_text()` and `embed_batch()`. `embed_code_elements()` passes `RETRIEVAL_DOCUMENT` to `embed_batch()` internally.

### Anti-Pattern 4: Passing a Batch to litellm for gemini-embedding-001

**What people do:** Call `litellm.embedding(model=..., input=texts)` with a list of N texts, expecting batch processing.

**Why it's wrong:** gemini-embedding-001 accepts only a single input per request at the REST API level. Passing multiple inputs may silently fail or return incorrect results depending on the litellm version.

**Do this instead:** Loop over texts and call `litellm.embedding()` one input at a time. If batch behavior is needed, validate against the litellm version in use and check the actual response `len(response.data)` matches `len(input)`.

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single repo (hundreds of elements) | Loop-per-element works fine; indexing is ~minutes |
| Multi-repo (thousands of elements) | Consider batching with `asyncio`/`litellm.aembedding()` at index time; not needed for v1.1 |
| Live query path | Single `embed_text()` call per query — latency is ~100-200ms VertexAI API round-trip; acceptable |

### Scaling Priorities

1. **First bottleneck:** Index-time API throughput — 1 call per element is slow for large repos. Mitigation for v1.1: not in scope; reindexing is offline. Future: `aembedding()` concurrency.
2. **Second bottleneck:** Query embedding adds ~100-200ms latency per query round-trip. Mitigation: cache query embeddings (cache already exists in codebase).

---

## Sources

- Direct codebase analysis: `fastcode/embedder.py`, `fastcode/indexer.py`, `fastcode/retriever.py`, `fastcode/vector_store.py`, `fastcode/main.py`, `config/config.yaml` (HIGH confidence)
- litellm embedding API: https://docs.litellm.ai/docs/embedding/supported_embedding (HIGH confidence — official docs, current)
- litellm VertexAI embedding: https://docs.litellm.ai/docs/providers/vertex_embedding (HIGH confidence — official docs)
- litellm task_type support for Vertex: https://docs.litellm.ai/docs/providers/vertex — `task_type` listed as Vertex-specific param (HIGH confidence)
- gemini-embedding-001 output dimensions: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/text-embeddings-api — 3072 default, 768/1536/3072 supported via `output_dimensionality` (HIGH confidence — official docs)
- gemini-embedding-001 single-input-per-request limit: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings (HIGH confidence — official docs)
- task_type proxy bug (fixed): https://github.com/BerriAI/litellm/issues/17759 — closed and merged in PR #18042; direct SDK calls unaffected (MEDIUM confidence — issue closed, may be version-specific)
- 768-dim normalization requirement: Google documentation notes 3072-dim is pre-normalized; smaller dims need manual normalization. VectorStore already calls `faiss.normalize_L2()` in `add_vectors()`. (HIGH confidence)

---

*Architecture research for: FastCode v1.1 — CodeEmbedder migration to litellm.embedding() + VertexAI*
*Researched: 2026-02-25*
