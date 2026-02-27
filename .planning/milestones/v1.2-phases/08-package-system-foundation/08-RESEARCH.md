# Phase 8: Package System Foundation - Research

**Researched:** 2026-02-26
**Domain:** Python packaging — uv, pyproject.toml, PEP 735 dependency groups, hatchling editable installs
**Confidence:** HIGH

## Summary

Phase 8 replaces a flat `requirements.txt` with a proper `pyproject.toml` + `uv.lock` package system. The project currently has no `pyproject.toml`, no `setup.py`, and no build system at all — `fastcode/` is imported via Python path, not as an installed package. This phase makes `fastcode` installable as an editable package and reproduces that installation deterministically via a committed lockfile.

The core work is: (1) author `pyproject.toml` with hatchling as the build backend, (2) split the existing `requirements.txt` into runtime `[project.dependencies]` and dev-only `[dependency-groups] dev`, (3) run `uv lock` to generate `uv.lock`, (4) commit `uv.lock`, and (5) delete `requirements.txt`. The success criteria for this phase directly test the boundary between runtime and dev installs — `uv sync --no-dev` must exclude pytest — so the dependency split must be accurate.

No CONTEXT.md exists for this phase. The key locked decision from STATE.md is that PKG-01 requires hatchling editable install: `[build-system]` with hatchling must be present so `fastcode` is importable as an installed package (not just a path import). The Dockerfile upgrade (PKG-05, PKG-06, PKG-07) is deferred to Phase 9.

**Primary recommendation:** Author `pyproject.toml` manually (do not use `uv init` — it would create scaffold files not wanted here), run `uv lock`, commit `uv.lock`, delete `requirements.txt`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PKG-01 | Developer can install runtime deps + fastcode (editable) with `uv sync`; `pyproject.toml` includes `[build-system]` with hatchling so `fastcode` is importable as installed package | Hatchling `[build-system]` block + `[project]` table + `uv sync` editable install pattern |
| PKG-02 | Dev/test deps (pytest, pytest-asyncio, pytest-cov) isolated in `[dependency-groups] dev`; excluded from prod via `UV_NO_DEV=1` | PEP 735 `[dependency-groups]` + `uv sync --no-dev` / `UV_NO_DEV=1` env var |
| PKG-03 | `uv.lock` committed to repository; reproducible builds across environments | `uv lock` generates cross-platform lockfile; must be committed, not gitignored |
| PKG-04 | `requirements.txt` deleted; `pyproject.toml` + `uv.lock` are sole authoritative dependency files | Delete file + verify `git ls-files requirements.txt` returns nothing |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| uv | 0.10.x (installed: 0.10.4) | Package manager, lockfile, venv management | Replaces pip + pip-tools; `uv sync` is the single install command |
| hatchling | latest (uv resolves) | Build backend for editable install | PEP 517/518 compliant; minimal config; uv recommends it; PKG-01 requires it |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PEP 735 `[dependency-groups]` | N/A (spec) | Standardized dev-dep isolation | Use for `dev` group containing pytest, pytest-asyncio, pytest-cov |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `[dependency-groups] dev` | `[project.optional-dependencies] dev` | Optional deps get published to PyPI; dependency-groups are local-only — correct choice for dev tools |
| hatchling | setuptools, flit, pdm-backend | Hatchling is uv's recommended default; minimal config for simple packages; STATE.md locks this choice |
| Manual `pyproject.toml` | `uv init` | `uv init` creates `.python-version`, `README.md`, `hello.py` scaffold — unwanted for existing project |

## Architecture Patterns

### Recommended pyproject.toml Structure

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "fastcode"
version = "2.0.0"
description = "Repository-level code understanding system"
requires-python = ">=3.12"
dependencies = [
    # ... runtime deps from requirements.txt (all non-test packages)
]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5",
]
```

### Pattern 1: Editable Install via hatchling `[build-system]`

**What:** Presence of `[build-system]` with hatchling causes `uv sync` to install the project itself as an editable package (pip-style `-e .`). Without `[build-system]`, uv treats the directory as a "virtual project" — no package installation, only dependency resolution.

**When to use:** Always — PKG-01 explicitly requires this so `import fastcode` works after a clean `uv sync`.

**Example:**
```toml
# Source: https://github.com/astral-sh/uv docs + pypa/hatch docs
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

After `uv sync`, the `.venv` will contain `fastcode` as an editable install:
```
.venv/lib/python3.12/site-packages/fastcode.pth  # points to repo root
```

### Pattern 2: PEP 735 `[dependency-groups]` for dev isolation

**What:** `[dependency-groups]` table (PEP 735) separates local dev tools from published runtime deps. The `dev` group is special-cased by uv — it is included by default during `uv sync` and `uv run` but excluded by `uv sync --no-dev` or env var `UV_NO_DEV=1`.

**When to use:** For pytest, pytest-asyncio, pytest-cov — anything not needed to run fastcode in production.

```toml
# Source: https://github.com/astral-sh/uv/blob/main/docs/concepts/projects/dependencies.md
[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5",
]
```

Verification:
```bash
uv sync --no-dev
python -m pytest  # must ImportError — pytest not installed
```

### Pattern 3: Generating and committing `uv.lock`

**What:** `uv lock` resolves all deps (runtime + all groups) and writes `uv.lock`. This is a cross-platform universal lockfile — one file covers all OS/arch combinations. Must be committed to git.

```bash
uv lock           # generates or updates uv.lock
git add uv.lock
```

The `.gitignore` currently lists `poetry.lock` but not `uv.lock` — `uv.lock` is NOT ignored and should be committed as-is.

### Pattern 4: Dependency migration from requirements.txt

**What:** The existing `requirements.txt` splits cleanly into runtime and dev:

- **Runtime** (→ `[project.dependencies]`): all packages except pytest, pytest-asyncio, pytest-cov
- **Dev** (→ `[dependency-groups] dev`): pytest, pytest-asyncio, pytest-cov

`uv add -r requirements.txt` can import from requirements.txt in bulk but requires an existing `pyproject.toml`. Manual authoring is more controlled and avoids uv adding unintended version pins.

### Anti-Patterns to Avoid

- **Using `[project.optional-dependencies]` for dev tools:** Optional deps are intended for PyPI extras (`pip install mypackage[dev]`). For internal dev tools, `[dependency-groups]` is correct (PEP 735).
- **Omitting `[build-system]`:** Without it, uv treats the project as a "virtual project" — `fastcode` package is NOT installed, only its dependencies. PKG-01 fails.
- **Committing `.venv/`:** The `.gitignore` already excludes `.venv` — verify this is not accidentally adding it.
- **Using `uv init` on an existing project:** Creates unwanted scaffold files and may overwrite existing content.
- **Using `UV_NO_DEV=1` in pyproject.toml:** This is an environment variable for runtime use (e.g., Dockerfile). It is NOT a pyproject.toml setting.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-platform lockfile | Custom requirements pinning per OS | `uv.lock` (universal resolution) | uv resolves across all platforms automatically |
| Editable install plumbing | Sys.path manipulation, .pth files | hatchling + `[build-system]` | Build backends handle editable installs correctly per PEP 660 |
| Dev dep isolation | `if DEV: pip install pytest` | `[dependency-groups] dev` + `uv sync --no-dev` | uv natively excludes dev groups from production installs |

**Key insight:** The entire phase is configuration authoring + one CLI command (`uv lock`). There is nothing to build from scratch — uv handles all the complexity of dependency resolution, virtual env management, and lockfile generation.

## Common Pitfalls

### Pitfall 1: `hatchling` doesn't find the `fastcode` package

**What goes wrong:** `uv sync` installs editable but `import fastcode` fails at import time with `ModuleNotFoundError`.

**Why it happens:** Hatchling auto-discovers packages in the project root. If `fastcode/__init__.py` exists at the root level (which it does in this project), hatchling will find it. But if hatchling is configured with a `src/` layout or non-standard paths, discovery fails.

**How to avoid:** This project has `fastcode/` at the repo root (not under `src/`). Hatchling auto-discovery handles this correctly with zero configuration. Do NOT add `[tool.hatch.build]` unless tests confirm auto-discovery fails.

**Warning signs:** After `uv sync`, check:
```bash
python -c "import fastcode; print(fastcode.__file__)"
```
Should print a path ending in `fastcode/__init__.py` in the repo.

### Pitfall 2: `uv.lock` gitignored by accident

**What goes wrong:** `git ls-files uv.lock` returns nothing (PKG-03 fails).

**Why it happens:** The `.gitignore` has `poetry.lock` listed — a developer might add `*.lock` thinking it covers poetry. The existing `.gitignore` does NOT have `uv.lock` or `*.lock` patterns that would match it, so this pitfall is low-risk for this project. Verify before committing.

**How to avoid:** After `uv lock`, run `git ls-files uv.lock` before pushing. If empty, the file is ignored — add `!uv.lock` to `.gitignore`.

### Pitfall 3: Version constraints too tight or too loose

**What goes wrong:** `uv lock` fails to resolve, or lockfile pins an incompatible version.

**Why it happens:** `requirements.txt` has `litellm[google]>=1.80.8` — this is a lower bound. Other packages (faiss-cpu, chromadb, tree-sitter-*) have no version pins in requirements.txt. `uv` will resolve to latest compatible versions.

**How to avoid:** For runtime deps from requirements.txt, carry over existing constraints as-is. Let uv resolve the rest. Review `uv lock` output for conflicts. If resolution fails, add upper bounds only where uv reports conflicts.

### Pitfall 4: `uv sync --no-dev` test (PKG-02 success criterion 2)

**What goes wrong:** `uv sync --no-dev && python -m pytest` does NOT fail — pytest is still present (maybe from system Python or another install).

**Why it happens:** `python -m pytest` in the PKG-02 success criterion runs against the venv created by `uv sync --no-dev`. If pytest is accidentally in `[project.dependencies]` instead of `[dependency-groups] dev`, it will be present.

**How to avoid:** Verify pytest, pytest-asyncio, pytest-cov appear ONLY in `[dependency-groups] dev`. After `uv sync --no-dev`, run:
```bash
.venv/bin/python -m pytest  # must be ImportError, not pytest
```
Use the venv's python directly (not system `python`) to avoid false negatives.

### Pitfall 5: Python version mismatch between hatchling editable and runtime

**What goes wrong:** `uv sync` uses Python 3.13 (system default) but Dockerfile targets Python 3.12.

**Why it happens:** No `.python-version` file exists in the repo. uv uses the system Python if not constrained.

**How to avoid:** Set `requires-python = ">=3.12"` in `[project]`. Optionally create `.python-version` with `3.12` to pin uv's venv Python. The Dockerfile already uses `python:3.12-slim-bookworm`. Note: a `.python-version` file is a PKG-F02 future requirement, not in scope for Phase 8 — but `requires-python = ">=3.12"` in pyproject.toml is in scope and sufficient.

## Code Examples

Verified patterns from official sources:

### Complete pyproject.toml for this project

```toml
# Source: https://github.com/astral-sh/uv docs, https://context7.com/pypa/hatch/llms.txt
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "fastcode"
version = "2.0.0"
description = "Repository-level code understanding system with multi-repository support"
requires-python = ">=3.12"
dependencies = [
    "python-dotenv",
    "pyyaml",
    "click",
    "gitpython",
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
    "faiss-cpu",
    "chromadb",
    "rank-bm25",
    "networkx",
    "tiktoken",
    "litellm[google]>=1.80.8",
    "fastapi",
    "uvicorn",
    "pydantic",
    "flask",
    "flask-cors",
    "python-multipart",
    "tqdm",
    "numpy",
    "pandas",
    "pathspec",
    "diskcache",
    "redis",
    "mcp[cli]",
]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5",
]
```

### Install workflow (developer)

```bash
# Source: https://docs.astral.sh/uv/guides/projects/
uv sync            # installs runtime deps + dev group + fastcode editable
uv sync --no-dev   # installs runtime deps + fastcode editable only (no pytest)
```

### Generate and commit lockfile

```bash
# Source: https://github.com/astral-sh/uv/blob/main/docs/concepts/projects/sync.md
uv lock                        # generates uv.lock from pyproject.toml
git add uv.lock pyproject.toml
git rm requirements.txt
git ls-files uv.lock           # must print: uv.lock
```

### Verify PKG-02 success criterion

```bash
# Success criterion: uv sync --no-dev && python -m pytest fails with ImportError
uv sync --no-dev
.venv/bin/python -m pytest
# Expected: /Users/.../python: No module named pytest
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `requirements.txt` + `pip install -r` | `pyproject.toml` + `uv sync` | uv GA 2024 | Single file, lockfile, editable install, dev isolation |
| Separate `requirements-dev.txt` | `[dependency-groups] dev` (PEP 735) | PEP 735 ratified 2024, uv >=0.4.27 | Standardized, tooling-native dev dep isolation |
| `setup.py` editable install | PEP 660 editable install via build backend | pip 21.3+ / PEP 660 2021 | `pip install -e .` via backend, not legacy |
| `pip freeze > requirements.txt` | `uv lock` | uv 2024 | Cross-platform universal lockfile, not per-machine freeze |

**Deprecated/outdated:**
- `requirements.txt` as authoritative dep file: replaced by `pyproject.toml` + `uv.lock`
- `[project.optional-dependencies]` for dev tools: superseded by `[dependency-groups]` (PEP 735) for non-published dependencies
- `tool.uv.dev-dependencies`: older uv-specific dev dep syntax; PEP 735 `[dependency-groups]` is now standard and preferred

## Open Questions

1. **Does hatchling auto-discover `fastcode/` at the repo root correctly?**
   - What we know: Hatchling auto-discovers packages by looking for directories with `__init__.py` at `dev-mode-dirs = ["."]` (the default). `fastcode/__init__.py` exists at the repo root.
   - What's unclear: Whether any other top-level packages (e.g., `tests/`, `nanobot/`) might also get picked up. `tests/__init__.py` exists.
   - Recommendation: After `uv sync`, run `python -c "import fastcode"` to verify. If hatchling picks up `tests` as a package too, add `[tool.hatch.build.targets.wheel] packages = ["fastcode"]` to scope the install.

2. **Should `mcp[cli]` be a runtime or optional dependency?**
   - What we know: `mcp_server.py` is at the root, not part of the `fastcode` package. The requirements.txt lists `mcp[cli]` under "MCP Server".
   - What's unclear: Whether MCP server functionality is always required or optional at runtime.
   - Recommendation: Keep in `[project.dependencies]` for Phase 8 (match current requirements.txt behavior). Optimization can happen later.

3. **`redis` runtime dependency — is it always required?**
   - What we know: `redis` is in requirements.txt with no comment indicating it's optional.
   - What's unclear: Whether `redis` is always available in all deployment environments.
   - Recommendation: Keep in `[project.dependencies]` to preserve current behavior. No scope to change this in Phase 8.

## Sources

### Primary (HIGH confidence)
- `/astral-sh/uv` (Context7) — pyproject.toml structure, `uv sync`, `uv lock`, `--no-dev`, `UV_NO_DEV`, `[dependency-groups]`, lockfile commit behavior
- `/pypa/hatch` (Context7) — hatchling build-system configuration, editable install, dev-mode-dirs
- https://docs.astral.sh/uv/guides/projects/ — uv working on projects guide
- https://github.com/astral-sh/uv/blob/main/docs/concepts/projects/dependencies.md — dependency groups documentation

### Secondary (MEDIUM confidence)
- https://til.simonwillison.net/uv/dependency-groups — practical PEP 735 dependency groups walkthrough (2025-12-02, recent)
- https://stackoverflow.com/questions/78902565 — confirmed `uv sync --no-dev` excludes `dev` group; verified with official uv docs
- https://www.prefect.io/blog/switching-a-big-python-library-from-setup-py-to-pyproject-toml — real-world requirements.txt → pyproject.toml migration with hatchling + uv

### Tertiary (LOW confidence)
- None required — all critical claims verified with primary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — uv and hatchling confirmed via Context7 official docs; version confirmed via `uv --version`
- Architecture: HIGH — pyproject.toml patterns verified via Context7; `[dependency-groups]` behavior confirmed via official uv docs
- Pitfalls: MEDIUM/HIGH — hatchling auto-discovery and gitignore pitfalls verified; version mismatch pitfall confirmed by Dockerfile inspection

**Research date:** 2026-02-26
**Valid until:** 2026-03-28 (uv moves fast; verify uv version in Dockerfile before Phase 9)
