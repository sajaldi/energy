# 💻 Instalación y Configuración Local

Sigue esta guía para configurar y levantar tu entorno local de desarrollo en Windows para el proyecto **Energy**.

## 📋 Prerrequisitos
- **Python**: Versión 3.9 o superior
- **Redis**: Instalado y corriendo en el puerto por defecto `6379`
- **Git**: Para control de versiones

## 🚀 Pasos de Instalación

### 1. Clonar el repositorio y acceder a él
```bash
git clone <url-repositorio>
cd energy
```

### 2. Configurar el Entorno Virtual (Virtualenv)
En Windows, crea y activa tu entorno virtual:
```powershell
python -m venv env
.\env\Scripts\activate
```

### 3. Instalar Dependencias
Instala todas las dependencias listadas en el archivo `requirements.txt`:
```powershell
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno
Copia el archivo `.env.example` como `.env` y rellena las variables de configuración local:
```powershell
copy .env.example .env
```
Asegura configurar los siguientes campos básicos para desarrollo:
- `DEBUG=True`
- `DATABASE_URL` (Dejar en blanco si usarás base de datos SQLite local o configurar acceso SSH para la base de datos externa de la planta).
- `CELERY_BROKER_URL=redis://localhost:6379/0`

### 5. Aplicar Migraciones y Cargar Semillas
```powershell
python manage.py migrate
```

---

## 🏃 Servidores en Ejecución (Entorno de Desarrollo)

Para levantar el ecosistema completo en tu máquina de desarrollo local, requieres abrir **3 terminales independientes** (con el entorno virtual activo):

### 🌐 Terminal 1: Servidor Django Web
Levanta el servidor de desarrollo web:
```powershell
python manage.py runserver
```
Acceso: [http://localhost:8000](http://localhost:8000)

### ⚙️ Terminal 2: Celery Worker (Tareas en background)
Inicia el worker de Celery con el pool `eventlet` para Windows:
```powershell
celery -A energia worker -l info -P eventlet
```

### ⏰ Terminal 3: Celery Beat (Planificador de Tareas)
Inicia el planificador periódico de rutinas (OTs preventivas automáticas):
```powershell
celery -A energia beat -l info
```

---
🔙 Volver a [[00_Inicio|Inicio]]
