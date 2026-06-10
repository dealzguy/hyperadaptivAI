# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

WORKDIR /app

# Install uv — MIT licensed; fetched as a binary, not linked into the harness.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifest and lockfile first for layer caching.
COPY pyproject.toml uv.lock ./

# Install production dependencies from the frozen lockfile.
RUN uv sync --frozen --no-dev

# Copy source.
COPY src/ ./src/

# Run the Temporal worker.
CMD ["uv", "run", "python", "-m", "harness.worker"]
