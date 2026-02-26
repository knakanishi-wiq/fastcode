---
phase: 07-dependency-cleanup-and-smoke-test
plan: "01"
subsystem: infra
tags: [sentence-transformers, litellm, vertexai, docker, requirements, embedding]

# Dependency graph
requires:
  - phase: 06-embedder-migration
    provides: CodeEmbedder rewritten to use litellm.embedding() — sentence-transformers runtime eliminated
provides:
  - requirements.txt without sentence-transformers line
  - Dockerfile without pre-bake 470MB model download layer
  - main.py _get_default_config() returning vertex_ai/gemini-embedding-001 with embedding_dim/normalize_embeddings
affects: [smoke-test, docker-build, config-absent deploys]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Default embedding config matches config/config.yaml — vertex_ai/gemini-embedding-001 with embedding_dim: 3072"
    - "Dockerfile layer order: system deps -> pip install -> mkdir -> COPY (no model pre-bake)"

key-files:
  created: []
  modified:
    - requirements.txt
    - fastcode/main.py
    - Dockerfile

key-decisions:
  - "R8+R10 committed atomically — prevents window where requirements.txt lacks sentence-transformers but main.py still defaults to a sentence-transformers model string"
  - "ENV TOKENIZERS_PARALLELISM=false left in Dockerfile — harmless no-op, out of scope per R9 specification"
  - ".pyc binary in __pycache__ still contains old sentence-transformers string — stale compiled cache, not source; clean on next Python run; out of scope"

patterns-established:
  - "Default config embedding block: model + embedding_dim + batch_size + normalize_embeddings (no device key)"

requirements-completed: [R8, R9, R10]

# Metrics
duration: 2min
completed: 2026-02-25
---

# Phase 7 Plan 01: Dependency Cleanup Summary

**sentence-transformers purged from requirements.txt, Dockerfile pre-bake layer removed, and main.py default config updated to vertex_ai/gemini-embedding-001 with embedding_dim/normalize_embeddings**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-25T09:48:50Z
- **Completed:** 2026-02-25T09:50:46Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Removed `sentence-transformers` from requirements.txt — pip install no longer pulls torch/transformers transitively
- Updated `_get_default_config()` embedding block in main.py: `vertex_ai/gemini-embedding-001`, `embedding_dim: 3072`, `normalize_embeddings: True`, no `device` key
- Removed 3-line Dockerfile pre-bake block (comments + RUN sentence_transformers download) — docker build no longer downloads a 470MB model layer
- Updated stale COPY comment from "won't re-download the model" to "Copy application code"

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove sentence-transformers from requirements.txt and update main.py defaults (R10+R8)** - `6ccda4d` (feat)
2. **Task 2: Remove Dockerfile pre-bake layer and orphaned comments (R9)** - `8e22591` (feat)

## Files Created/Modified
- `requirements.txt` - Removed `sentence-transformers` line from Embeddings & Vector Store section
- `fastcode/main.py` - Updated `_get_default_config()` embedding block to VertexAI defaults
- `Dockerfile` - Removed pre-bake RUN layer and updated stale COPY comment

## Decisions Made
- R8 and R10 committed together atomically to prevent a window where requirements.txt lacks sentence-transformers but main.py still references it as default — would cause a confusing litellm BadRequestError on config-absent deploys
- `ENV TOKENIZERS_PARALLELISM=false` left in Dockerfile per R9 specification (harmless no-op, out of scope)
- `__pycache__/main.cpython-313.pyc` still contains old string — stale compiled cache artifact predating Phase 6; will be regenerated on next Python run; not a source file concern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `grep -rn "sentence-transformers/" fastcode/` matched a binary `.pyc` file in `__pycache__/` — confirmed `.py` source files are clean via `--include="*.py"` flag. Cache artifact is pre-existing and out of scope.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All three requirements (R8, R9, R10) satisfied
- Codebase fully free of sentence-transformers references in source and dependency manifests
- Ready for Phase 7 Plan 02 (smoke test)

---
*Phase: 07-dependency-cleanup-and-smoke-test*
*Completed: 2026-02-25*
