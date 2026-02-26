# Architecture Research

**Domain:** Python packaging migration — requirements.txt + pip + Dockerfile to pyproject.toml + uv.lock + uv Dockerfile
**Researched:** 2026-02-26
**Confidence:** HIGH (sourced from official uv documentation at docs.astral.sh/uv)

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Project Root                            │
├─────────────────────────────────────────────────────────────┤
│  pyproject.toml    uv.lock      Dockerfile    .dockerignore  │
│  (deps + meta)     (locked)     (uv-based)    (.venv excluded)│
├─────────────────────────────────────────────────────────────┤
│                  Build / Install Flow                         │
├────────────────────┬────────────────────────────────────────┤
│   Local Dev        │           Docker Build                   │
│  uv sync           │  COPY uv binary                         │
│  (all groups)      │  → uv sync --locked --no-dev            │
│                    │                                          │
│  uv sync --group   │  Layer 1: deps only (cache hit on       │
│   test             │    source-only changes)                  │
│                    │  Layer 2: COPY source + project sync    │
└────────────────────┴────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | What Changes |
|-----------|----------------|--------------|
| `pyproject.toml` | Project metadata + all dependency declarations (runtime, dev, test) | NEW — replaces `requirements.txt` |
| `uv.lock` | Exact pinned versions, cross-platform lockfile | NEW — committed to git |
| `Dockerfile` | Multi-layer uv install pattern with cache mounts | MODIFIED — replaces `pip install -r requirements.txt` |
| `requirements.txt` | Runtime dependency list | DELETE after migration |
| `.dockerignore` | Exclude `.venv` from build context | ADD or MODIFY |
| `.venv/` | Local virtual environment | LOCAL ONLY — never committed, never in Docker image |

---

## Recommended Project Structure

```
FastCode/                      # project root
├── pyproject.toml             # NEW: replaces requirements.txt
├── uv.lock                    # NEW: committed lockfile
├── Dockerfile                 # MODIFIED: uv-based install
├── .dockerignore              # ADD/MODIFY: exclude .venv
├── docker-compose.yml         # UNCHANGED
├── requirements.txt           # DELETE: after pyproject.toml migration
├── fastcode/                  # UNCHANGED: application package
│   └── ...
├── tests/                     # UNCHANGED: pytest test suite
│   └── ...
├── api.py                     # UNCHANGED
├── main.py                    # UNCHANGED
└── config/                    # UNCHANGED
```

### Structure Rationale

- **pyproject.toml at root:** uv requires it at the project root to identify the project. It sits alongside `uv.lock` so both are at the same level.
- **requirements.txt deleted:** After `uv add -r requirements.txt` completes and `uv.lock` is generated, `requirements.txt` serves no further purpose. Keeping it causes confusion about which file is authoritative.
- **uv.lock committed:** The lockfile is cross-platform and must be committed for reproducible builds in CI and Docker. It is managed automatically by uv — never edit manually.
- **.venv never committed or in Docker image:** The virtual environment is platform-specific. Docker builds recreate it from scratch via `uv sync`.

---

## Architectural Patterns

### Pattern 1: pyproject.toml with Dependency Groups

**What:** Runtime deps in `[project.dependencies]`, test-only deps in a named `[dependency-groups]` section. FastCode is a deployed service (not a published library), so `[dependency-groups]` (PEP 735, local-only) is correct — these deps are never published to PyPI.

**When to use:** This project. `[project.optional-dependencies]` is for published package extras (e.g., `pip install fastcode[plot]`). `[dependency-groups]` is for local tooling and test deps that should never be in the production container.

**Trade-offs:**
- The `dev` group is the uv default — it installs automatically with `uv sync`. The `test` group must be explicitly requested with `--group test`.
- `--no-dev` in the Dockerfile excludes the default `dev` group. The `test` group is already excluded by default (non-dev groups are opt-in).

**Example:**
```toml
[project]
name = "fastcode"
version = "1.2.0"
description = "Code intelligence backend with RAG pipeline and agentic retrieval"
requires-python = ">=3.12"
dependencies = [
    # Core
    "python-dotenv",
    "pyyaml",
    "click",
    # Repository Management
    "gitpython",
    # Code Parsing
    "tree-sitter",
    "tree-sitter-python",
    "tree-sitter-javascript",
    "tree-sitter-typescript",
    "tree-sitter-java",
    "tree-sitter-go",
    "tree-sitter-c",
    "tree-sitter-cpp",
    "tree-sitter-rust",
    "tree-sitter-c-sharp",
    "libcst",
    # Embeddings & Vector Store
    "faiss-cpu",
    "chromadb",
    # Search & Retrieval
    "rank-bm25",
    "networkx",
    # LLM Integration
    "tiktoken",
    "litellm[google]>=1.80.8",
    # API
    "fastapi",
    "uvicorn",
    "pydantic",
    "flask",
    "flask-cors",
    "python-multipart",
    # Utilities
    "tqdm",
    "numpy",
    "pandas",
    "pathspec",
    # Caching
    "diskcache",
    "redis",
    # MCP Server
    "mcp[cli]",
]

[dependency-groups]
test = [
    "pytest",
    "pytest-asyncio",
    "pytest-cov",
]
# dev group left empty for now; add linting tools here later if needed

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Pattern 2: uv Dockerfile with Intermediate Layer Caching

**What:** Copy the uv binary into the existing `python:3.12-slim-bookworm` base image (not switching to a uv-derived base). Use bind mounts for `pyproject.toml` and `uv.lock` in an intermediate layer to install deps before copying source code.

**When to use:** Always for Docker builds. The intermediate layer technique means Docker only re-downloads dependencies when `uv.lock` or `pyproject.toml` changes — not on every source code change.

**Trade-offs:**
- `--mount=type=cache` requires Docker BuildKit (enabled by default in Docker 23+; set `DOCKER_BUILDKIT=1` on older versions)
- Pinning the uv version (`uv:0.6.x`) prevents surprise breakage; `uv:latest` is convenient but can silently break builds on uv updates
- `UV_COMPILE_BYTECODE=1` increases build time slightly but improves container startup time
- `UV_LINK_MODE=copy` avoids spurious warnings when the uv cache mount is on a different filesystem than the install target

**Example (full Dockerfile for FastCode):**
```dockerfile
FROM python:3.12-slim-bookworm

# Copy uv binary from official image — pin to specific version for reproducibility
COPY --from=ghcr.io/astral-sh/uv:0.6.0 /uv /uvx /bin/

# Compile bytecode for faster startup; copy mode avoids cross-filesystem link warnings
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install system dependencies for tree-sitter and git (same as before)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        build-essential \
        curl \
        ca-certificates && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Layer 1: Install runtime dependencies only, before copying source.
# This layer is cached as long as pyproject.toml and uv.lock do not change.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Layer 2: Copy source and install the project itself
COPY fastcode/ fastcode/
COPY api.py ./
COPY config/ config/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Activate the venv by prepending its bin dir to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Create necessary directories
RUN mkdir -p /app/repos /app/data /app/logs

EXPOSE 8001
ENV PYTHONUNBUFFERED=1
# TOKENIZERS_PARALLELISM=false removed — dead code after sentence-transformers removal

CMD ["python", "api.py", "--host", "0.0.0.0", "--port", "8001"]
```

### Pattern 3: uv binary via COPY vs ghcr.io/astral-sh/uv base image

**What:** Two approaches for getting uv into a Docker build:

1. `COPY --from=ghcr.io/astral-sh/uv:VERSION /uv /uvx /bin/` — copies the uv binary into your own base image (recommended for FastCode)
2. `FROM ghcr.io/astral-sh/uv:debian AS builder` — uses a uv-provided image as the base

**When to use:** Option 1 (COPY binary into existing base) is correct for FastCode because:
- The current Dockerfile uses `python:3.12-slim-bookworm` and installs apt packages (`git`, `build-essential`)
- Option 1 keeps the known-good base image — only one Dockerfile line changes to add uv
- Option 2 requires auditing which Python version and Debian variant the uv-provided image uses

**Trade-offs:** Option 1 adds one `COPY --from` line and is otherwise orthogonal to base image choice. Option 2 reduces the Dockerfile to pure uv-speak but risks Python version drift if the uv base image updates its Python.

---

## Data Flow

### Dependency Resolution Flow

```
requirements.txt (source of truth today)
    |
    v (one-time migration command)
uv add -r requirements.txt
    |
    v (generates both files)
pyproject.toml + uv.lock
    |
    +-----> local dev:   uv sync           (installs runtime + default dev group into .venv)
    |
    +-----> local test:  uv sync --group test (runtime + test group into .venv)
    |
    +-----> docker prod: uv sync --locked --no-dev (runtime only into /app/.venv)
    |
    +-----> CI:          uv sync --locked --group test (runtime + test group)
```

### Docker Build Layer Flow

```
Layer 1: Base image (python:3.12-slim-bookworm)
    |
Layer 2: apt packages (git, build-essential, curl, ca-certificates)
          [cache: invalidated rarely — only on apt changes]
    |
Layer 3: uv binary COPY --from=ghcr.io/astral-sh/uv:0.6.0
          [cache: invalidated only on uv version pin change]
    |
Layer 4: uv sync --locked --no-install-project --no-dev
          [cache: invalidated only when pyproject.toml or uv.lock changes]
    |
Layer 5: COPY source (fastcode/, api.py, config/)
          [cache: invalidated on any source change]
    |
Layer 6: uv sync --locked --no-dev (installs the project package itself)
    |
Final image
```

### Key Data Flows

1. **Migration (one-time):** Run `uv add -r requirements.txt` at project root. uv reads requirements.txt, resolves all deps, writes `pyproject.toml`, and generates `uv.lock`. Manually move pytest/pytest-asyncio/pytest-cov to `[dependency-groups] test`. Delete `requirements.txt` after verifying.
2. **Lockfile update:** `uv lock` regenerates `uv.lock` from `pyproject.toml` constraints. Commit `uv.lock` changes alongside `pyproject.toml` changes in the same commit.
3. **Adding a new dep:** `uv add <package>` — updates both `pyproject.toml` and `uv.lock` atomically. `uv add --group test pytest-mock` adds to the test group.
4. **Running tests:** `uv run --group test pytest` or `uv sync --group test && pytest` — installs the test group before running.

---

## Integration Points

### Files: New vs Modified vs Unchanged

| File | Status | What Changes |
|------|--------|--------------|
| `requirements.txt` | DELETE | Replaced entirely by pyproject.toml + uv.lock |
| `pyproject.toml` | NEW | All runtime deps, project metadata, test dependency group |
| `uv.lock` | NEW | Committed lockfile, auto-managed by uv |
| `Dockerfile` | MODIFIED | Replace `pip install -r requirements.txt` with uv pattern (see Pattern 2) |
| `.dockerignore` | ADD/MODIFY | Add `.venv` exclusion |
| `docker-compose.yml` | UNCHANGED | No changes needed — Docker build is internal detail |
| `fastcode/` package | UNCHANGED | No packaging code changes |
| `tests/` | UNCHANGED | pytest invocation unchanged; `uv run pytest` or `uv sync --group test && pytest` |
| `api.py`, `main.py` | UNCHANGED | Application entry points unchanged |
| `config/` | UNCHANGED | Configuration files unchanged |

### Dev/Test Extras Separation

| Group | Contents | Install Command | Used In |
|-------|----------|----------------|---------|
| Runtime (`[project.dependencies]`) | All 30+ runtime deps | `uv sync --no-dev` | Docker production |
| `test` (`[dependency-groups]`) | pytest, pytest-asyncio, pytest-cov | `uv sync --group test` | CI / local test runs |
| `dev` (default group, optional) | Empty for now; add linting tools if desired | `uv sync` (installed by default) | Local dev |

The `test` group is explicitly separate from the default `dev` group. The `--no-dev` flag in the Dockerfile excludes only the default `dev` group. The `test` group is already excluded in Docker by default (non-dev groups require explicit `--group test` to install).

### .dockerignore Required Additions

```
.venv
__pycache__
*.pyc
*.pyo
.git
.pytest_cache
```

### PATH Activation in Docker

uv sync creates `.venv` inside `WORKDIR` (`/app/.venv`). Set `ENV PATH="/app/.venv/bin:$PATH"` after the final sync — this makes `python`, `uvicorn`, and other venv executables available directly in `CMD` and subsequent `RUN` instructions without needing `uv run`.

---

## Anti-Patterns

### Anti-Pattern 1: Copying .venv into Docker Image

**What people do:** Run `uv sync` locally, then `COPY .venv /app/.venv` in the Dockerfile to skip the sync step inside Docker.

**Why it's wrong:** The local `.venv` is platform-specific (macOS vs Linux). Copying it into a Linux container causes binary incompatibilities for packages with native extensions (faiss-cpu, tree-sitter compiled grammars, libcst).

**Do this instead:** Add `.venv` to `.dockerignore`. Always run `uv sync` inside the Docker build to create a Linux-native venv.

### Anti-Pattern 2: Installing uv via pip or curl inside Dockerfile

**What people do:** `RUN pip install uv` or `RUN curl -LsSf https://astral.sh/uv/install.sh | sh` inside the Dockerfile.

**Why it's wrong:** `pip install uv` installs uv as a Python package (slower, awkward version pinning). The curl installer adds complexity and a network dependency at build time without a pinned version.

**Do this instead:** `COPY --from=ghcr.io/astral-sh/uv:0.6.0 /uv /uvx /bin/` — copies the statically linked uv binary directly from the official image. Pin the version tag for reproducibility.

### Anti-Pattern 3: Not Committing uv.lock

**What people do:** Add `uv.lock` to `.gitignore` (treating it like `node_modules` or `.venv`).

**Why it's wrong:** Without a committed lockfile, `uv sync --locked` fails in Docker builds (the `--locked` flag asserts the lockfile exists and is current). Without `--locked`, different Docker builds at different times may resolve different package versions, breaking reproducibility.

**Do this instead:** Commit `uv.lock`. It is a text file, diffable, and managed automatically by uv commands. Never edit it manually.

### Anti-Pattern 4: Keeping requirements.txt Alongside pyproject.toml

**What people do:** Keep `requirements.txt` as a backup or for tools that don't support pyproject.toml yet.

**Why it's wrong:** Two authoritative dependency files will drift. The old Dockerfile line `pip install -r requirements.txt` will silently ignore pyproject.toml if not updated. CI or Docker might use one, developers the other.

**Do this instead:** Delete `requirements.txt` in the same commit that adds `pyproject.toml` and `uv.lock`. If a tool needs a requirements file, generate it on the fly: `uv export --no-dev > requirements.txt` (but do not commit the output).

### Anti-Pattern 5: Using uv:latest in Dockerfile

**What people do:** `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/`

**Why it's wrong:** `latest` resolves to a different version on every build. A uv update with breaking changes can silently break Docker builds with no diff in the repository.

**Do this instead:** Pin to a specific version: `COPY --from=ghcr.io/astral-sh/uv:0.6.0 /uv /uvx /bin/`. Update the pin deliberately when upgrading uv.

### Anti-Pattern 6: Putting Test Deps in [project.dependencies]

**What people do:** Leave pytest/pytest-asyncio/pytest-cov in `[project.dependencies]` after migrating from requirements.txt (where they were mixed with runtime deps).

**Why it's wrong:** Test deps bloat the production Docker image. Every `pip install fastcode` (or `uv sync`) install installs pytest unnecessarily in production containers.

**Do this instead:** Move pytest, pytest-asyncio, pytest-cov to `[dependency-groups] test = [...]`. They will be excluded automatically from Docker builds using `--no-dev` (since `test` is not the default `dev` group, it's excluded by default without needing any flag).

---

## Build Order for Migration

Dependencies dictate this sequence:

**Step 1 — Generate pyproject.toml and uv.lock from requirements.txt**

```bash
# At project root
uv init --no-workspace  # creates pyproject.toml skeleton if not present
uv add -r requirements.txt  # migrates all deps; generates uv.lock
```

**Step 2 — Move test deps from [project.dependencies] to [dependency-groups]**

Edit `pyproject.toml` manually:
- Remove `pytest`, `pytest-asyncio`, `pytest-cov` from `[project.dependencies]`
- Add `[dependency-groups]` section with `test = ["pytest", "pytest-asyncio", "pytest-cov"]`
- Run `uv lock` to regenerate `uv.lock` reflecting the move

**Step 3 — Rewrite Dockerfile**

Replace the `pip install -r requirements.txt` block with the uv pattern from Pattern 2 above. Remove `ENV TOKENIZERS_PARALLELISM=false` (dead code after v1.1).

**Step 4 — Add/update .dockerignore**

Add `.venv`, `__pycache__`, `*.pyc`, `.pytest_cache` entries.

**Step 5 — Delete requirements.txt**

```bash
git rm requirements.txt
```

**Step 6 — Verify**

```bash
# Local install
uv sync              # installs runtime + default dev group
uv sync --group test # adds test group

# Run tests
uv run --group test pytest

# Build Docker image
docker build -t fastcode:test .

# Verify no test deps in image
docker run --rm fastcode:test python -c "import pytest" && echo "FAIL: pytest in prod image"
```

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single developer | `uv sync` for local dev; `uv sync --group test` before running tests |
| CI pipeline | `uv sync --locked --group test`; `--locked` ensures lockfile is in sync |
| Multi-platform Docker builds | `uv.lock` is cross-platform; same lockfile works for both amd64 and arm64 builds |

### Scaling Priorities

1. **First concern:** Layer cache invalidation. The intermediate layer (deps only, before source COPY) is the biggest win — ensures `docker build` doesn't re-download 30+ packages on every source change.
2. **Second concern:** uv version pinning. Pin early, update deliberately. `latest` will cause problems at the worst possible time.

---

## Sources

- [uv Docker integration guide](https://docs.astral.sh/uv/guides/integration/docker/) — HIGH confidence, official docs
- [uv project layout concepts](https://docs.astral.sh/uv/concepts/projects/layout/) — HIGH confidence, official docs
- [uv dependency groups and optional deps](https://docs.astral.sh/uv/concepts/projects/dependencies/) — HIGH confidence, official docs
- [uv project guide with migration from requirements.txt](https://docs.astral.sh/uv/guides/projects/) — HIGH confidence, official docs
- ghcr.io/astral-sh/uv Docker image — HIGH confidence (referenced in official uv docs)

---

*Architecture research for: FastCode v1.2 — uv migration (pyproject.toml + uv.lock + Dockerfile)*
*Researched: 2026-02-26*
