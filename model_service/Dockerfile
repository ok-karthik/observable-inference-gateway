FROM python:3.14-slim-bookworm as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set virtual environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock /app/

# Install packages
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Multi-stage docker builds
FROM python:3.14-slim-bookworm as runner

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

# Set virtual environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Create a non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

COPY --chown=appuser:appuser . /app/

EXPOSE 8001
CMD ["opentelemetry-instrument", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]