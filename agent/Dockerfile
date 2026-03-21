FROM python:3.12-slim AS base

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# System deps for Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl wget gnupg \
    # Chromium dependencies
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libpangocairo-1.0-0 libgtk-3-0 libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

FROM base AS builder
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install "." --target /install

FROM base AS runtime
COPY --from=builder /install /usr/local/lib/python3.12/site-packages

# Install Playwright browsers
RUN pip install playwright==1.44.0 && \
    playwright install chromium

COPY . .

RUN adduser --disabled-password --gecos "" --uid 1001 agentuser
USER agentuser

ARG BUILD_VERSION=dev
ENV BUILD_VERSION=$BUILD_VERSION

CMD ["python", "-m", "agent.worker"]
