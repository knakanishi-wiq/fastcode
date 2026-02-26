# Deferred Items — Phase 06 Embedder Migration

## Out-of-Scope Pre-existing Issue

**File:** fastcode/__init__.py
**Issue:** `import platform` exists for setting tokenizer env vars on macOS (TOKENIZERS_PARALLELISM, OMP_NUM_THREADS, etc.)
**Why deferred:** Pre-existing code unrelated to embedder migration. These env vars were originally for sentence-transformers tokenizer parallelism. With sentence-transformers removed, these vars may no longer be needed. However, they are harmless and removing them was outside the scope of plan 06-01.
**Suggested follow-up:** Remove the platform import and env var block from fastcode/__init__.py in a cleanup pass if confirmed no other dependency requires them.
