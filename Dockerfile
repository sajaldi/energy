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



# Puerto que usaremos para correr gunicorn (Coolify suele usar 3000 por defecto)
EXPOSE 3000

# Ejecutar migraciones y levantar gunicorn
# Usamos shell form para permitir variable de expansión
CMD sh -c "python manage.py collectstatic --noinput && python manage.py migrate && gunicorn energia.wsgi:application --bind 0.0.0.0:${PORT:-8000}"
