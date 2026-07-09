# ===== STAGE 1: Builder =====
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev pkg-config libcairo2-dev python3-dev \
    && rm -rf /var/lib/apt/lists/*

# CRÍTICO: copiar requirements ANTES del código para máximo cache
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Playwright — solo se re-ejecuta si requirements.txt cambia
RUN playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/*

# ===== STAGE 2: Runtime =====
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Runtime deps mínimos
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 postgresql-client libcairo2 fonts-liberation curl \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Capas pesadas del builder — se cachean si requirements.txt no cambió
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /root/.cache/ms-playwright/ /root/.cache/ms-playwright/

RUN mkdir -p /app/media /app/staticfiles

# Código fuente — única capa que cambia en CADA deploy
COPY . /app/

# Pre-compilar archivos .py a bytecode para arranque más rápido
RUN python -m compileall -q /app/ 2>/dev/null || true

RUN chmod +x /app/start.sh

EXPOSE 8000
CMD ["/bin/bash", "/app/start.sh"]
