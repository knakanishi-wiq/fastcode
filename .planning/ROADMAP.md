# Roadmap: FastCode — LiteLLM Provider Migration

## Milestones

- ✅ **v1.0 LiteLLM Provider Migration** — Phases 1–5 (shipped 2026-02-25)
- ✅ **v1.1 VertexAI Embedding Migration** — Phases 6–7 (shipped 2026-02-25)
- 🚧 **v1.2 uv Migration & Tech Debt Cleanup** — Phases 8–10 (in progress)

## Phases

<details>
<summary>✅ v1.0 LiteLLM Provider Migration (Phases 1–5) — SHIPPED 2026-02-25</summary>

- [x] Phase 1: Config and Dependencies (1/1 plans) — completed 2026-02-24
- [x] Phase 2: Core Infrastructure (2/2 plans) — completed 2026-02-24
- [x] Phase 3: Non-Streaming Migration (4/4 plans) — completed 2026-02-24
- [x] Phase 4: Streaming Migration and Finalization (2/2 plans) — completed 2026-02-25
- [x] Phase 5: Fix answer_generator.py Wiring and Cleanup (1/1 plan) — completed 2026-02-25

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 VertexAI Embedding Migration (Phases 6–7) — SHIPPED 2026-02-25</summary>

- [x] Phase 6: Embedder Migration (1/1 plans) — completed 2026-02-25
- [x] Phase 7: Dependency Cleanup and Smoke Test (2/2 plans) — completed 2026-02-25

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

### 🚧 v1.2 uv Migration & Tech Debt Cleanup (In Progress)

**Milestone Goal:** Replace requirements.txt + pip with pyproject.toml + uv.lock + uv Dockerfile; close four open tech debt items from v1.1; consolidate env var configuration.

- [x] **Phase 8: Package System Foundation** — Create pyproject.toml, generate uv.lock, delete requirements.txt (2 plans) (completed 2026-02-26)
- [x] **Phase 9: Dockerfile and Code Cleanup** — Update Dockerfile to use uv, remove dead code, make task_type explicit (completed 2026-02-26)
- [ ] **Phase 10: Config Consolidation and Verification** — Consolidate MODEL/LITELLM_MODEL env vars; verify CODE_RETRIEVAL_QUERY and streaming behavior live

## Phase Details

### Phase 8: Package System Foundation
**Goal**: Developer can install FastCode and its dependencies reproducibly using `uv sync` from a committed lockfile
**Depends on**: Nothing (first phase of v1.2)
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04
**Success Criteria** (what must be TRUE):
  1. `uv sync` from a clean checkout installs all runtime deps and the fastcode package (editable) without errors
  2. `uv sync --no-dev && python -m pytest` fails with ImportError (pytest not present in runtime install)
  3. `git ls-files uv.lock` returns the file path (lockfile is committed, not gitignored)
  4. `requirements.txt` no longer exists in the repository
**Plans**: 2 plans

Plans:
- [ ] 08-01-PLAN.md — Author pyproject.toml + generate uv.lock (PKG-01, PKG-02, PKG-03)
- [ ] 08-02-PLAN.md — Delete requirements.txt + run phase verification (PKG-04)

### Phase 9: Dockerfile and Code Cleanup
**Goal**: Docker builds use uv with layer caching, dead code is removed, and task_type intent is visible at all call sites
**Depends on**: Phase 8 (uv.lock must exist in VCS before Dockerfile can reference it)
**Requirements**: PKG-05, PKG-06, PKG-07, DEBT-01, DEBT-02
**Success Criteria** (what must be TRUE):
  1. Changing only a `.py` source file and rebuilding Docker produces no package download output (layer 4 cache hit)
  2. Production Docker image has no pytest, pytest-asyncio, or pytest-cov installed (`pip show pytest` returns error inside container)
  3. `fastcode/__init__.py` contains no OS-detection or `TOKENIZERS_PARALLELISM` platform import block
  4. `retriever.py` line 415 passes `task_type="RETRIEVAL_QUERY"` as an explicit keyword argument
**Plans**: 2 plans

Plans:
- [ ] 09-01-PLAN.md — Rewrite Dockerfile with uv two-layer cache pattern (PKG-05, PKG-06, PKG-07)
- [ ] 09-02-PLAN.md — Remove dead platform block from __init__.py; explicit task_type in retriever.py (DEBT-01, DEBT-02)

### Phase 10: Config Consolidation and Verification
**Goal**: A single env var controls the active model, and both CODE_RETRIEVAL_QUERY task_type and streaming chunk boundary behavior are verified live
**Depends on**: Phase 9
**Requirements**: DEBT-04, DEBT-03, DEBT-05
**Success Criteria** (what must be TRUE):
  1. `.env.example` references exactly one model env var; `answer_generator.py` and all other LLM callers read from the same variable
  2. A live smoke test confirms `CODE_RETRIEVAL_QUERY` task_type at `retriever.py` line 734 works end-to-end with gemini-embedding-001
  3. A live multi-turn session confirms `_stream_with_summary_filter()` handles SUMMARY tag chunk boundary splits correctly; result is captured as a test note
**Plans**: 2 plans

Plans:
- [ ] 10-01-PLAN.md — Consolidate MODEL/LITELLM_MODEL: update answer_generator.py + .env.example (DEBT-04)
- [ ] 10-02-PLAN.md — Add CODE_RETRIEVAL_QUERY and streaming filter smoke tests (DEBT-03, DEBT-05)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Config and Dependencies | v1.0 | 1/1 | Complete | 2026-02-24 |
| 2. Core Infrastructure | v1.0 | 2/2 | Complete | 2026-02-24 |
| 3. Non-Streaming Migration | v1.0 | 4/4 | Complete | 2026-02-24 |
| 4. Streaming Migration and Finalization | v1.0 | 2/2 | Complete | 2026-02-25 |
| 5. Fix answer_generator.py Wiring | v1.0 | 1/1 | Complete | 2026-02-25 |
| 6. Embedder Migration | v1.1 | 1/1 | Complete | 2026-02-25 |
| 7. Dependency Cleanup and Smoke Test | v1.1 | 2/2 | Complete | 2026-02-25 |
| 8. Package System Foundation | 2/2 | Complete    | 2026-02-26 | - |
| 9. Dockerfile and Code Cleanup | 2/2 | Complete    | 2026-02-26 | - |
| 10. Config Consolidation and Verification | 1/2 | In Progress|  | - |
