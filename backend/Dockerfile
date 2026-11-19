# Stage 1: Builder
FROM python:3.14.9-slim-bookworm AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/

# Environment tuning for uv inside Docker
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/sonclarus/.venv

ENV PATH="/sonclarus/.venv/bin:$PATH" \
    PYTHONPATH="/sonclarus" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /sonclarus

# Reuse the dependency layer while the project manifest and lockfile are unchanged.
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# --- copy application code ---
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.14.9-slim-bookworm AS runtime

# Install PostgreSQL client for the service healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user.
RUN groupadd --gid 1000 sonclarus && \
    useradd --uid 1000 --gid sonclarus --shell /bin/bash --create-home sonclarus

WORKDIR /sonclarus

# Copy the built environment and only the runtime files.
COPY --from=builder --chown=sonclarus:sonclarus /sonclarus/.venv ./.venv
COPY --from=builder --chown=sonclarus:sonclarus /sonclarus/src ./src
COPY --from=builder --chown=sonclarus:sonclarus /sonclarus/alembic ./alembic
COPY --from=builder --chown=sonclarus:sonclarus /sonclarus/alembic.ini ./alembic.ini

ENV PATH="/sonclarus/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/sonclarus"

USER sonclarus

EXPOSE 8000

CMD ["uvicorn", "src.sonclarus.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
