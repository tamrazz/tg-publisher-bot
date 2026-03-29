# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Base: Python + ffmpeg (required by yt-dlp audio extraction)
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ---------------------------------------------------------------------------
# Builder: install dependencies
# ---------------------------------------------------------------------------
FROM base AS builder

# Model name must match settings.whisper_model default (overridable at build time)
ARG WHISPER_MODEL=base
ENV HF_HOME=/app/.cache/huggingface

COPY pyproject.toml .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir ".[dev]"

# Pre-download the faster-whisper model so runtime never needs to write to /root/.cache.
# The read_only container can still read from the image layer at /app/.cache.
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8')" 2>&1 | grep -v "^$" || true

# ---------------------------------------------------------------------------
# Development image
# ---------------------------------------------------------------------------
FROM builder AS dev

COPY . .

CMD ["python", "-m", "src"]

# ---------------------------------------------------------------------------
# Production image (no dev deps)
# ---------------------------------------------------------------------------
FROM base AS prod

ENV HF_HOME=/app/.cache/huggingface

# Copy installed packages and pre-downloaded model cache from builder
COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/.cache /app/.cache

COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini .

# Run migrations then start bot
CMD ["sh", "-c", "alembic upgrade head && python -m src"]
