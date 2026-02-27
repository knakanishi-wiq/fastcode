FROM python:3.12-slim-bookworm

# Install system dependencies for tree-sitter and git
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        build-essential \
        curl \
        ca-certificates && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Install uv (pinned to 0.10.6 per project decision)
COPY --from=ghcr.io/astral-sh/uv:0.10.6 /uv /uvx /bin/

WORKDIR /app

# Exclude dev deps from all uv sync calls (no pytest in production)
ENV UV_NO_DEV=1
# Copy mode required for Docker overlay filesystem (prevents hardlink warnings)
ENV UV_LINK_MODE=copy
# Use OS native TLS (OpenSSL) instead of rustls, so system CA store is respected
ENV UV_NATIVE_TLS=1

# ARG busts the cache for the secret layer when switching between local/cloud builds.
# Local: pass --build-arg CERT=1; cloud: omit (defaults to empty, caches as no-op).
# Docker only keys on ARGs that are referenced inside a RUN — the `: "${CERT}"` expands
# the variable (shell no-op) so Docker includes its value in the layer cache key.
ARG CERT=
# Inject corporate CA if provided (for SSL-inspecting proxies); no-op in cloud build
RUN --mount=type=secret,id=corporate_ca,required=false \
    : "${CERT}" && \
    if [ -f /run/secrets/corporate_ca ]; then \
        cp /run/secrets/corporate_ca /usr/local/share/ca-certificates/corporate.crt && \
        update-ca-certificates; \
    fi

# Layer 3: Install dependencies only (cached unless pyproject.toml or uv.lock change)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Layer 4: Install project source (cache invalidated on .py changes; packages not re-downloaded)
COPY pyproject.toml uv.lock ./
COPY fastcode/ fastcode/
COPY api.py ./
COPY config/ config/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Runtime directories
RUN mkdir -p /app/repos /app/data /app/logs

# Default port for FastCode API
EXPOSE 8001

# Environment defaults (can be overridden in docker-compose)
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "api.py", "--host", "0.0.0.0", "--port", "8001"]
