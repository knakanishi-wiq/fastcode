# Pitfalls Research

**Domain:** Python packaging migration — requirements.txt to uv (pyproject.toml + uv.lock)
**Project:** FastCode — v1.2 uv Migration & Tech Debt Cleanup
**Researched:** 2026-02-26
**Confidence:** HIGH (official uv docs verified; specific package behavior MEDIUM where wheel availability varies by platform)

---

## Critical Pitfalls

### Pitfall 1: uv.lock Added to .gitignore — Defeats the Entire Point of uv

**What goes wrong:**
Developer adds `uv.lock` to `.gitignore` thinking "lockfiles are machine-specific" (conflating with `node_modules` or `__pycache__`). CI installs whatever the latest resolution produces, not what was tested locally. Production image may install different package versions than development.

**Why it happens:**
`.python-version` and `.venv/` should be gitignored, and those look similar to `uv.lock`. Muscle memory from Python workflow where `requirements.txt` was the pinned file and a separate `requirements.in` was the source of truth — in uv, `pyproject.toml` is the "requirements.in" equivalent and `uv.lock` is the "requirements.txt" equivalent.

**How to avoid:**
Commit `uv.lock` to git. uv docs are explicit: "The lockfile should be checked into version control, allowing for consistent and reproducible installations across machines."

Correct `.gitignore` additions for a uv project:
```
.venv/
*.pyc
__pycache__/
```

Do NOT add `uv.lock` to `.gitignore`.

**Warning signs:**
- CI produces different package versions than local dev
- `uv sync --locked` fails in CI ("lockfile does not match")
- `uv.lock` never appears in git status after `uv lock` runs

**Phase to address:**
Phase 1 (pyproject.toml + uv.lock setup). Verify `git status` shows `uv.lock` as tracked before proceeding.

---

### Pitfall 2: Extras Syntax Works in pyproject.toml BUT Version Constraints Must Not Use `>=` With a Space

**What goes wrong:**
`requirements.txt` allows `litellm[google]>=1.80.8` with no quoting concerns. In `pyproject.toml`, PEP 508 dependency strings inside TOML arrays must be quoted strings, and the entire spec is one string. The extras bracket syntax is the same, but common mistakes occur with spacing and quotes:

```toml
# WRONG — unquoted
dependencies = [
  litellm[google]>=1.80.8,
]

# WRONG — missing closing quote
dependencies = [
  "litellm[google]>=1.80.8,
]

# CORRECT
dependencies = [
  "litellm[google]>=1.80.8",
]
```

`uv add` handles this correctly when using the CLI. The issue arises only when hand-editing `pyproject.toml` or using `uv add -r requirements.txt` and then manually modifying the output.

**Why it happens:**
TOML string syntax is unfamiliar to developers coming from requirements.txt. PEP 508 extras and version specs look like they might be TOML syntax but they are string content.

**How to avoid:**
Use `uv add "litellm[google]>=1.80.8"` for all packages with extras — let uv write the pyproject.toml entry. Verify the result in `pyproject.toml` has the entry as a quoted string. For the full migration from `requirements.txt`, use `uv add -r requirements.txt` which handles the translation.

**Warning signs:**
- `uv lock` fails with a TOML parse error
- Package installs without its extras (i.e., `litellm` installs but `google-cloud-aiplatform` is missing)
- `uv add --dry-run litellm[google]` shows different deps than expected

**Phase to address:**
Phase 1 (pyproject.toml authoring). Validate by running `uv sync` and checking that `google-cloud-aiplatform` appears in `.venv`.

---

### Pitfall 3: Dev Dependencies in Wrong Section — pytest and test deps as Runtime Dependencies

**What goes wrong:**
`requirements.txt` does not distinguish dev from runtime — everything is one flat list. When migrating, the naive path is `uv add -r requirements.txt`, which puts `pytest`, `pytest-asyncio`, `pytest-cov` into `[project.dependencies]` (runtime). These then get installed in the production Docker image, bloating it unnecessarily.

FastCode's `requirements.txt` mixes: `pytest`, `pytest-asyncio`, `pytest-cov` (test-only) with runtime packages.

**Why it happens:**
`uv add -r requirements.txt` has no way to know which packages are dev-only — it adds everything to `[project.dependencies]` unless told otherwise.

**How to avoid:**
For FastCode specifically, add test packages to the `dev` dependency group:
```bash
uv add --dev pytest pytest-asyncio pytest-cov
```

This creates a `[dependency-groups]` section in `pyproject.toml`:
```toml
[dependency-groups]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "pytest-cov>=5",
]
```

In Docker production builds, exclude dev deps:
```dockerfile
RUN uv sync --locked --no-dev
```

**Warning signs:**
- Docker image is larger than expected (pytest installed in production)
- `uv sync --no-dev` still installs test packages
- `uv tree` shows pytest as a runtime dependency

**Phase to address:**
Phase 1 (pyproject.toml setup). Verify by running `uv sync --no-dev` and confirming pytest is absent from `.venv`.

---

### Pitfall 4: Docker Layer Cache Broken — Copying All Source Before Dependencies

**What goes wrong:**
The current Dockerfile pattern:
```dockerfile
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .
```
migrates naively to:
```dockerfile
COPY . .
RUN uv sync --locked
```

This breaks layer caching: any source code change invalidates the dependency installation layer, causing a full `uv sync` on every build even when `pyproject.toml` and `uv.lock` haven't changed.

**Why it happens:**
`uv sync` needs `pyproject.toml` AND `uv.lock` AND the project source (to install the project itself). Developers copy all files before syncing to satisfy all requirements in one step.

**How to avoid:**
Split into two sync operations using `--no-install-project`:
```dockerfile
COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /uvx /bin/

ENV UV_LINK_MODE=copy

# Step 1: Install deps only (this layer caches until pyproject.toml or uv.lock changes)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project

# Step 2: Copy source and install the project itself
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev
```

The `--no-install-project` flag installs all dependencies but not the FastCode project package itself. The dependency layer only rebuilds when `pyproject.toml` or `uv.lock` changes.

**Warning signs:**
- Every Docker build takes the same time regardless of whether only Python code changed
- `uv sync` runs again even when only `fastcode/*.py` files changed
- Build logs show package downloads on code-only changes

**Phase to address:**
Phase 2 (Dockerfile migration). This is the single biggest Docker performance win from the uv migration.

---

### Pitfall 5: Missing UV_LINK_MODE=copy — Noisy Warnings With Cache Mounts

**What goes wrong:**
When using `--mount=type=cache` in Dockerfile, the uv cache directory and the virtual environment directory are on different filesystems. uv defaults to hard-linking files between cache and venv, which fails silently with repeated warnings like:
```
warning: Failed to hardlink files; falling back to full copy
```
This does not break the build but fills logs and slows builds slightly.

**Why it happens:**
Docker cache mounts create a separate tmpfs or overlay filesystem. Hard links cannot cross filesystem boundaries.

**How to avoid:**
Set `ENV UV_LINK_MODE=copy` in the Dockerfile before any `uv sync` commands. This tells uv to copy files instead of hard-link, which works across filesystem boundaries.

**Warning signs:**
- Dockerfile build output contains "Failed to hardlink" warnings
- Build is slower than expected despite cache mounts being used

**Phase to address:**
Phase 2 (Dockerfile migration). Add `ENV UV_LINK_MODE=copy` immediately after copying the uv binary.

---

### Pitfall 6: uv Sync Removes Packages Not in Lockfile — Breaks Existing Workflows That pip install Extras

**What goes wrong:**
`uv sync` performs exact environment synchronization: it **removes** packages present in `.venv` that are not in `uv.lock`. This differs fundamentally from `pip install`, which only adds packages. If any CI step or local workflow does `pip install some-tool` or `uv pip install something` after `uv sync`, the next `uv sync` will remove it.

**Why it happens:**
Developers coming from pip expect install commands to be additive. `uv sync` treats the lockfile as the complete truth about what should be installed.

**How to avoid:**
Never use `pip install` or `uv pip install` to add packages to the project environment. Always use `uv add` (updates `pyproject.toml` and `uv.lock`) or add packages to `[dependency-groups]`. For one-off tools, use `uvx tool` instead of installing into the project venv.

In CI, use `uv sync --locked` (strict lockfile) not `pip install -r requirements.txt` alongside `uv sync`.

**Warning signs:**
- Package disappears from venv after running `uv sync`
- CI fails because a package installed in an earlier step is no longer present
- `uv sync` output shows "Removed X" for a package you intentionally installed

**Phase to address:**
Phase 1 (migration). Document in project README that `uv add` replaces `pip install`.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `requirements.txt` alongside `pyproject.toml` for "compatibility" | Other tools still work with requirements.txt | Two sources of truth diverge silently; humans update the wrong one | Never — delete requirements.txt once pyproject.toml is validated |
| Use `uv pip install` in Dockerfile instead of `uv sync` | Familiar pip-like syntax | Bypasses lockfile; no reproducibility guarantee; no dev/prod separation | Never in production images |
| Pin uv version to `latest` in Dockerfile (`COPY --from=ghcr.io/astral-sh/uv:latest`) | Always gets latest uv features | Build breaks when uv releases a breaking change | Only in development; production images should pin to specific version |
| Put all deps (including pytest) in `[project.dependencies]` to avoid learning `[dependency-groups]` | Simpler migration | pytest and test infra installed in production container; potential for test code to accidentally import in production | Never |
| Skip `requires-python` in pyproject.toml | One less field to set | uv resolves deps for all Python versions, producing larger lockfile and potentially wrong wheels | Never for an app that knows its Python version |

---

## Integration Gotchas

Common mistakes when connecting to external systems or workflows.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Docker cache mounts | COPY all files before `uv sync` | Bind-mount only `pyproject.toml` + `uv.lock` for first sync; COPY source after |
| CI (GitHub Actions) | `pip install -r requirements.txt` in CI after migration | Replace with `uv sync --locked` |
| pytest execution | `python -m pytest` after `source .venv/bin/activate` | Use `uv run pytest` or activate venv correctly; `uv run` ensures sync before running |
| pre-commit hooks | Hook env uses system Python, not project venv | Configure pre-commit to use `uv run` or install hooks inside the venv |
| Docker CMD | `CMD ["python", "api.py"]` with no venv activation | Use `CMD ["/app/.venv/bin/python", "api.py"]` or `ENV PATH="/app/.venv/bin:$PATH"` |
| faiss-cpu native build | Missing build tools in Docker image | faiss-cpu ships wheels for major platforms — wheels install cleanly; only fails if building from source without `build-essential` |

---

## Performance Traps

Patterns that work but are slower than necessary.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| COPY before sync in Dockerfile | Full uv sync on every code change during Docker build | Use `--no-install-project` two-step pattern | Every build after initial setup |
| `uv sync` without cache mount in Docker | Full package download on every CI run | Add `--mount=type=cache,target=/root/.cache/uv` | CI becomes slow as package count grows |
| Missing `--compile-bytecode` in production image | Import time is slightly slower; `SyntaxWarning` may appear | Set `ENV UV_COMPILE_BYTECODE=1` | Not a hard failure, but noticeable in production startup latency |
| Running `uv lock` without `--locked` check in CI | Lock file can drift from `pyproject.toml` silently | Run `uv lock --locked` in CI to assert lockfile is current | When developer forgets to commit updated `uv.lock` after `uv add` |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Pinning uv to `latest` in production Dockerfile | Supply chain: `latest` tag can change; untested uv version auto-deploys | Pin to specific uv version: `COPY --from=ghcr.io/astral-sh/uv:0.10.4` |
| Not using `--locked` in production syncs | Different package versions may install than were tested | Always use `uv sync --locked` in CI and Docker; `--frozen` is weaker (skips staleness check) |
| Committing `.venv/` to git accidentally | Can include platform-specific compiled binaries; large repo pollution | uv auto-creates `.venv/.gitignore` to block this, but verify `.gitignore` at project root excludes `.venv/` |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **pyproject.toml created:** Verify `uv sync` actually installs all packages — run `python -c "import faiss; import tree_sitter; import litellm; import mcp"` inside `.venv`
- [ ] **Dev deps separated:** Verify `uv sync --no-dev` does NOT install pytest — run `uv sync --no-dev && python -m pytest --collect-only` should fail with ModuleNotFoundError
- [ ] **uv.lock committed:** Run `git status` and confirm `uv.lock` is tracked (not in `.gitignore`)
- [ ] **Dockerfile layer caching works:** Change a `.py` file only and rebuild Docker — the `uv sync --no-install-project` step should use cache (no package downloads in output)
- [ ] **Docker CMD uses venv Python:** Run `docker exec <container> which python` — should return `/app/.venv/bin/python`, not `/usr/bin/python`
- [ ] **requirements.txt deleted:** Confirm no stale `requirements.txt` that could mislead future developers
- [ ] **CI updated:** CI workflow file uses `uv sync --locked`, not `pip install -r requirements.txt`
- [ ] **Tree-sitter packages install correctly:** These are compiled packages — verify `import tree_sitter_python` succeeds post-migration (wheel-only, no source build needed for common platforms)

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| uv.lock in .gitignore and diverged | MEDIUM | Remove from .gitignore, run `uv lock`, commit uv.lock, verify CI passes |
| Wrong packages in runtime deps (pytest in prod) | LOW | `uv remove pytest pytest-asyncio pytest-cov && uv add --dev pytest pytest-asyncio pytest-cov` |
| Docker cache never hits | LOW | Add `--no-install-project` two-step pattern; rebuild from scratch once to establish cache |
| Package missing extras (litellm missing google deps) | LOW | `uv remove litellm && uv add "litellm[google]>=1.80.8"` |
| requirements.txt still present and diverged | LOW | Delete requirements.txt; ensure all deps are in pyproject.toml; run `uv lock` |
| uv.lock conflicts after parallel branch merges | LOW | Run `uv lock` on the merged branch to regenerate; commit result |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| uv.lock in .gitignore | Phase 1: pyproject.toml + uv.lock setup | `git ls-files uv.lock` returns the file path |
| Extras syntax wrong in pyproject.toml | Phase 1: pyproject.toml authoring | `uv run python -c "from litellm import completion"` succeeds; `google-cloud-aiplatform` in `.venv` |
| Dev deps in wrong section | Phase 1: dependency group setup | `uv sync --no-dev && python -m pytest` fails with ImportError |
| Docker layer cache broken | Phase 2: Dockerfile migration | Touch `fastcode/main.py`, rebuild Docker; no package downloads in output |
| UV_LINK_MODE missing | Phase 2: Dockerfile migration | No "Failed to hardlink" warnings in Docker build output |
| uv sync removes packages | Phase 1: migration docs | `uv add` replaces `pip install` in all developer docs and CI scripts |

---

## Specific Package Notes

### litellm[google]
- The `[google]` extra installs `google-cloud-aiplatform` and related GCP packages. This extra is large (~150MB transitive deps). Confirm it appears in `uv.lock` after adding.
- In pyproject.toml: `"litellm[google]>=1.80.8"` — extras bracket syntax is identical to requirements.txt.
- Confidence: HIGH (tested syntax; PEP 508 extras work in pyproject.toml dependencies arrays)

### mcp[cli]
- The `[cli]` extra adds CLI tooling for the MCP server. Same bracket syntax applies.
- In pyproject.toml: `"mcp[cli]"` — no version pin needed unless a specific version is required.
- Confidence: HIGH

### faiss-cpu
- faiss-cpu ships binary wheels for `linux/amd64`, `macos/arm64`, `macos/x86_64`, and `win/amd64` for Python 3.8–3.12.
- No source build required — uv will resolve the appropriate wheel automatically.
- If building on a platform without a wheel (e.g., `linux/arm64`), build will fail unless `build-essential` is installed and faiss can be compiled from source. FastCode's Dockerfile uses `python:3.12-slim-bookworm` on amd64, which has wheels available.
- Confidence: MEDIUM (wheel availability for common platforms is well-established; ARM Linux is a known gap)

### tree-sitter and language packages (tree-sitter-python, tree-sitter-javascript, etc.)
- All tree-sitter language packages (tree-sitter-python, tree-sitter-javascript, etc.) ship compiled wheels for common platforms since tree-sitter 0.21+.
- These are wheel-only installs — no source compilation needed on supported platforms.
- The `build-essential` and `git` packages already present in the Dockerfile cover the edge case where a source build is needed.
- Confidence: MEDIUM (wheel availability confirmed for major platforms; edge cases on older Python/platform combos)

### pytest and test packages
- `pytest`, `pytest-asyncio`, `pytest-cov` must go in `[dependency-groups] dev`, NOT `[project.dependencies]`.
- In uv: `uv add --dev pytest pytest-asyncio pytest-cov`
- Confidence: HIGH

---

## Sources

- uv Docker integration guide: https://docs.astral.sh/uv/guides/integration/docker/ (HIGH confidence — official docs)
- uv migration guide (pip to project): https://docs.astral.sh/uv/guides/migration/pip-to-project/ (HIGH confidence — official docs)
- uv project dependencies: https://docs.astral.sh/uv/concepts/projects/dependencies/ (HIGH confidence — official docs)
- uv pip compatibility: https://docs.astral.sh/uv/pip/compatibility/ (HIGH confidence — official docs)
- uv Python version management: https://docs.astral.sh/uv/concepts/python-versions/ (HIGH confidence — official docs)
- uv project init: https://docs.astral.sh/uv/concepts/projects/init/ (HIGH confidence — official docs)
- uv sync behavior: https://docs.astral.sh/uv/concepts/projects/sync/ (HIGH confidence — official docs)
- uv settings reference: https://docs.astral.sh/uv/reference/settings/ (HIGH confidence — official docs)
- Current requirements.txt analysis: /Users/knakanishi/Repositories/FastCode/requirements.txt (direct codebase inspection)
- Current Dockerfile analysis: /Users/knakanishi/Repositories/FastCode/Dockerfile (direct codebase inspection)
- uv version in environment: 0.10.4 (Homebrew 2026-02-17) — confirmed installed

---
*Pitfalls research for: uv packaging migration (requirements.txt → pyproject.toml + uv.lock)*
*Researched: 2026-02-26*
