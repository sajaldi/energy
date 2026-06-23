# ===== STAGE 1: Dependencias (sistema + Python + Playwright) =====
# Esta capa solo se reconstruye cuando cambian requirements.txt o playwright
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Dependencias del sistema (capa estable)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    postgresql-client \
    pkg-config \
    libcairo2-dev \
    python3-dev \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python (capa con caché, solo cambia con requirements.txt)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Playwright (capa separada, solo se reinstala si cambia playwright en requirements)
RUN playwright install --with-deps chromium

# ===== STAGE 2: Solo código fuente (capa ultra-ligera) =====
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Copiar site-packages y bins del stage builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /root/.cache/ms-playwright/ /root/.cache/ms-playwright/

# Copiar solo el código de la app (capa que cambia frecuentemente)
COPY . /app/

RUN mkdir -p /app/media /app/staticfiles

EXPOSE 8000
RUN chmod +x /app/start.sh

CMD ["/bin/bash", "/app/start.sh"]
