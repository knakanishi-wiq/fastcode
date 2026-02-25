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

WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir --retries 5 --timeout 60 -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/repos /app/data /app/logs

# Copy application code
COPY fastcode/ fastcode/
COPY api.py ./
COPY config/ config/

# Default port for FastCode API
EXPOSE 8001

# Environment defaults (can be overridden in docker-compose)
ENV PYTHONUNBUFFERED=1
ENV TOKENIZERS_PARALLELISM=false

CMD ["python", "api.py", "--host", "0.0.0.0", "--port", "8001"]
