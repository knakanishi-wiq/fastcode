# Requirements: FastCode

**Defined:** 2026-02-26
**Core Value:** All LLM and embedding calls in FastCode route through litellm, enabling full VertexAI on GCP via ADC without provider-specific client code.

## v1.2 Requirements

Requirements for the uv Migration & Tech Debt Cleanup milestone.

### Packaging (uv migration)

- [x] **PKG-01**: Developer can install runtime deps and the fastcode package (editable) with `uv sync` from `pyproject.toml` + `uv.lock`; `pyproject.toml` includes `[build-system]` with hatchling so `fastcode` is importable as an installed package
- [x] **PKG-02**: Dev/test deps (pytest, pytest-asyncio, pytest-cov) are isolated in `[dependency-groups] dev` and excluded from production installs via `UV_NO_DEV=1`
- [x] **PKG-03**: `uv.lock` lockfile is committed to the repository; builds are reproducible across environments
- [x] **PKG-04**: `requirements.txt` is deleted; `pyproject.toml` + `uv.lock` are the single authoritative dependency files
- [x] **PKG-05**: `Dockerfile` installs dependencies via `uv sync --frozen` with two-layer caching: layer 1 installs deps without project (`--no-install-project`), layer 2 installs the project itself
- [x] **PKG-06**: Docker builds exclude dev deps (`UV_NO_DEV=1`); production image has no pytest or test infrastructure
- [x] **PKG-07**: `ENV TOKENIZERS_PARALLELISM=false` removed from `Dockerfile` (dead env var after sentence-transformers removal in v1.1)

### Tech Debt (v1.1 cleanup)

- [x] **DEBT-01**: Dead platform import block removed from `fastcode/__init__.py` (OS-specific tokenizer env vars became no-ops after sentence-transformers removal)
- [x] **DEBT-02**: `retriever.py` line 415 passes `task_type="RETRIEVAL_QUERY"` explicitly instead of relying on the `embed_text()` default; intent visible at call site
- [ ] **DEBT-03**: `retriever.py` line 734 `CODE_RETRIEVAL_QUERY` confirmed valid for `gemini-embedding-001` via live smoke test; verified the asymmetric CODE_RETRIEVAL_QUERY (query) / RETRIEVAL_DOCUMENT (index) pairing works end-to-end
- [x] **DEBT-04**: `MODEL` and `LITELLM_MODEL` env vars consolidated into one; `.env.example` and `answer_generator.py` updated to use a single var; breaking change documented
- [ ] **DEBT-05**: `_stream_with_summary_filter()` chunk boundary behavior verified in a live multi-turn session; result captured as a test note or smoke test

## Future Requirements

### Packaging

- **PKG-F01**: GitHub Actions CI workflow added — runs `uv sync --locked` + pytest on push
- **PKG-F02**: `.python-version` file committed to pin Python 3.12 for uv tooling

### Tech Debt

- **DEBT-F01**: `fastcode/__init__.py` duplicate `FastCode = FastCode` assignment and duplicate `"FastCode"` in `__all__` cleaned up (pre-existing noise, not blocking)

## Out of Scope

| Feature | Reason |
|---------|--------|
| `src/` layout migration | No structural benefit for this app; editable install achieves same path-independence without directory reorganization |
| CI workflow (GitHub Actions) | No existing CI; adding it is a separate milestone concern |
| Publishing to PyPI | FastCode is an internal tool; installable package is for local editable install, not distribution |
| Upstream HKUDS/FastCode sync | Separate concern; v1.0/v1.1 changes would create significant merge conflicts |
| New retrieval features | Out of scope since v1.0 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PKG-01 | Phase 8 | Complete |
| PKG-02 | Phase 8 | Complete |
| PKG-03 | Phase 8 | Complete |
| PKG-04 | Phase 8 | Complete |
| PKG-05 | Phase 9 | Complete |
| PKG-06 | Phase 9 | Complete |
| PKG-07 | Phase 9 | Complete |
| DEBT-01 | Phase 9 | Complete |
| DEBT-02 | Phase 9 | Complete |
| DEBT-03 | Phase 10 | Pending |
| DEBT-04 | Phase 10 | Complete |
| DEBT-05 | Phase 10 | Pending |

**Coverage:**
- v1.2 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-26*
*Last updated: 2026-02-26 after roadmap creation (Phases 8–10)*
