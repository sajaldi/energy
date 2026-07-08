# ===== STAGE 1: Builder — solo se reconstruye si cambia requirements.txt =====
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Sistema — capa muy estable
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    pkg-config \
    libcairo2-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Python deps — cacheadas mientras requirements.txt no cambie
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Playwright — cacheado mientras la versión no cambie en requirements.txt
RUN playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/*

# ===== STAGE 2: Runtime — imagen mínima =====
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Solo las librerías runtime de sistema (sin build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    libcairo2 \
    fonts-liberation \
    # Deps de Chromium (runtime únicamente)
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copiar site-packages y binarios del builder (la parte pesada)
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /root/.cache/ms-playwright/ /root/.cache/ms-playwright/

# Crear dirs necesarios
RUN mkdir -p /app/media /app/staticfiles

# Copiar código fuente — única capa que cambia en cada deploy
# .dockerignore evita copiar .git, env/, node_modules, etc.
COPY . /app/

RUN chmod +x /app/start.sh

EXPOSE 8000

CMD ["/bin/bash", "/app/start.sh"]
