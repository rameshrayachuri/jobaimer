FROM python:3.12-slim AS base

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

FROM base AS builder
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install ".[dev]" --target /install

FROM base AS runtime
COPY --from=builder /install /usr/local/lib/python3.12/site-packages
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Non-root user for security
RUN adduser --disabled-password --gecos "" --uid 1001 appuser
USER appuser

ARG BUILD_VERSION=dev
ENV BUILD_VERSION=$BUILD_VERSION

# Lambda handler
CMD ["python", "-m", "awslambdaric", "app.main.handler"]
