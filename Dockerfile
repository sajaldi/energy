# Dockerfile

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Instalar dependencias del sistema que Django podría necesitar
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . /app/

# Recolectar archivos estáticos (opcional, si usas staticfiles)
RUN python manage.py collectstatic --noinput

# Puerto que usaremos para correr gunicorn
EXPOSE 8000

# Ejecutar migraciones y levantar gunicorn
CMD python manage.py migrate && gunicorn energy.wsgi:application --bind 0.0.0.0:8000
