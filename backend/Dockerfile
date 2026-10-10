# Stage 1: Builder
FROM python:3.14-slim AS builder

# Install uv via
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Environment tuning for uv inside Docker
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/sonclarus/.venv

ENV PATH="/sonclarus/.venv/bin:$PATH" \
    PYTHONPATH="/sonclarus/backend" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /sonclarus

# as long as requirements.txt doesn't change, Docker reuses this
COPY requirements.txt ./backend/requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /sonclarus/.venv && \
    /sonclarus/.venv/bin/pip install --no-cache-dir -r backend/requirements.txt

# --- copy application code ---
COPY src ./backend/src
COPY alembic ./backend/alembic
COPY alembic.ini ./backend/alembic.ini

# Stage 2: Runtime
FROM python:3.14-slim AS runtime

# Install postgresql-client for healthcheck and entrypoint
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd --gid 1000 sonclarus && \
    useradd --uid 1000 --gid sonclarus --shell /bin/bash --create-home sonclarus

WORKDIR /sonclarus

# Copy the built venv + app code from the builder stage
COPY --from=builder --chown=sonclarus:sonclarus /sonclarus/.venv ./.venv
COPY --from=builder --chown=sonclarus:sonclarus /sonclarus/backend/src ./backend/src
COPY --from=builder --chown=sonclarus:sonclarus /sonclarus/backend/alembic ./backend/alembic
COPY --from=builder --chown=sonclarus:sonclarus /sonclarus/backend/alembic.ini ./backend/alembic.ini

ENV PATH="/sonclarus/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/sonclarus/backend"

USER sonclarus

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "src.sonclarus.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]