import os
import sys
import django

# Bootstrap Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
try:
    django.setup()
except Exception as e:
    print(f"Error bootstrapping Django: {e}")
    sys.exit(1)

from django.apps import apps
from django.db import models

# List of local apps to document
LOCAL_APPS = [
    'core', 'documentos', 'comunicaciones', 'proyectos', 'activos', 
    'mantenimiento', 'presupuestos', 'inventarios', 'auditorias', 
    'seguridad', 'callcenter', 'servicios', 'almacen', 'iot'
]

# Mapping of apps to beautiful descriptive names
APP_NAMES = {
    'core': 'Núcleo del Sistema (Core)',
    'documentos': 'Gestión Documental',
    'comunicaciones': 'Comunicaciones e Hilos (Transmittals)',
    'proyectos': 'Gestión de Proyectos (CAPEX)',
    'activos': 'Gestión de Activos Industriales',
    'mantenimiento': 'Gestión de Mantenimiento (CMMS)',
    'presupuestos': 'Gestión Presupuestaria y Requisiciones',
    'inventarios': 'Inventarios y Materiales',
    'auditorias': 'Auditorías y Conciliación QR',
    'seguridad': 'Seguridad Industrial y Permisos de Trabajo',
    'callcenter': 'Call Center y Tickets de Soporte',
    'servicios': 'Servicios y KPIs',
    'almacen': 'Almacén y Bodegas Físicas',
    'iot': 'Mapeo IoT y Mediciones en Tiempo Real'
}

VAULT_DIR = os.path.join(os.getcwd(), 'docs', 'obsidian_vault')

def create_directories():
    """Create directory structure for Obsidian Vault"""
    os.makedirs(VAULT_DIR, exist_ok=True)
    for folder in ['01_Arquitectura', '02_Modulos', '03_Flujos_y_Procesos', '04_Operaciones']:
        os.makedirs(os.path.join(VAULT_DIR, folder), exist_ok=True)
    print(f"Obsidian Vault directory structure initialized at: {VAULT_DIR}")

def generate_static_files():
    """Generate curated non-dynamic markdown files with diagrams and guides"""
    
    # 1. 00_Inicio.md (Dashboard Map of Content)
    inicio_content = """# ⚡ Ecosistema Industrial Energy - SoftCom-CCG

> [!NOTE]
> Bienvenido al **Wiki interactivo de Obsidian** para el sistema **Energy**. Este espacio consolida la arquitectura técnica, modelos de datos, flujos de trabajo asíncronos y guías operativas de la planta de energía.
>
> Usa el **Graph View** de Obsidian (Ctrl/Cmd + G) para navegar visualmente por las relaciones de los modelos y las integraciones del sistema.

---

## 🗺️ Mapa de Contenido (MOC)

```mermaid
graph TD
    classDef default fill:#1e1e2e,stroke:#cdd6f4,stroke-width:1px,color:#cdd6f4;
    classDef highlight fill:#f5c2e7,stroke:#cba6f7,stroke-width:2px,color:#11111b;
    
    Home["⚡ Energy Home"] --> ARQ["🏗️ 01. Arquitectura"]
    Home --> MOD["📂 02. Módulos & Modelos"]
    Home --> FLU["🔄 03. Flujos & Procesos"]
    Home --> OPE["⚙️ 04. Operaciones & DevOps"]
    
    class Home highlight;
```

### 🏗️ 01. Arquitectura del Sistema
- [[Arquitectura_General|📐 Arquitectura General e Infraestructura]]
- [[Base_de_Datos|🗄️ Base de Datos y Relaciones Core]]
- [[Servicios_y_Sistemas_Externos|☁️ Servicios y Sistemas Externos (MinIO, Celery, n8n, Dynamics)]]

### 📂 02. Módulos y Modelos de Datos (Django Apps)
Explora las notas individuales para cada módulo, que contienen la definición exacta de sus tablas, campos y relaciones:
- **Core / General**: [[Core|Núcleo del Sistema]] | [[Servicios_y_KPIs|Servicios & KPIs]]
- **Operaciones**: [[Activos|Gestión de Activos]] | [[Mantenimiento|Mantenimiento (CMMS)]] | [[Inventarios|Inventarios y Materiales]] | [[Almacen|Almacén]] | [[Auditorias|Auditorías]]
- **Seguridad**: [[Seguridad|Seguridad Industrial & Permisos]]
- **Finanzas**: [[Presupuestos|Presupuestos & Requisiciones]] | [[Proyectos|Gestión de Proyectos (CAPEX)]]
- **Soporte & Docs**: [[Documentos|Gestión Documental]] | [[Comunicaciones|Comunicaciones y Transmittals]] | [[CallCenter|Call Center / Tickets]]
- **Tecnología**: [[IoT|Mapeo IoT & Mediciones]]

### 🔄 03. Flujos y Procesos Complejos
Procedimientos paso a paso sobre el funcionamiento crítico del sistema:
- [[Conexion_DB_Remota|🔌 Conexión Remota a Base de Datos en VM]]
- [[Importacion_Asincrona_Celery|📥 Importaciones Masivas Asíncronas (Celery & Redis)]]
- [[Wizard_Seguridad_AST|🛡️ Wizard de Permisos de Trabajo & AST]]

### ⚙️ 04. Operaciones, Guía de Inicio y DevOps
- [[Instalacion_Local|💻 Instalación y Configuración Local]]
- [[Despliegue_Coolify|🚀 Especificaciones de Despliegue en Coolify / Docker]]

---
#django #industrial #cmms #obsidian #ecosistema
"""
    with open(os.path.join(VAULT_DIR, '00_Inicio.md'), 'w', encoding='utf-8') as f:
        f.write(inicio_content)

    # 2. 01_Arquitectura/Arquitectura_General.md
    arq_content = """# 📐 Arquitectura General e Infraestructura

El sistema **Energy** está diseñado bajo una arquitectura de micro-servicios y tareas desacopladas, lo que permite alta concurrencia en la planta, procesamiento en segundo plano de importaciones masivas y generación de firmas electrónicas sin interrumpir la experiencia de usuario.

## 🗺️ Mapa de Infraestructura y Servicios

```mermaid
graph TD
    subgraph Cliente ["💻 Clientes / Campo"]
        Web[💻 Navegador Web / Desktop]
        Mobile[📱 App Móvil / Escáner QR]
    end

    subgraph AppServer ["🚀 Servidor de Aplicación (Coolify)"]
        Django[🐍 Django Web Server]
        Celery[⚙️ Celery Worker]
        CeleryBeat[⏰ Celery Beat Scheduler]
    end

    subgraph Servicios ["⚡ Servicios e Integración"]
        Postgres[(🗄️ PostgreSQL)]
        Redis[(🧠 Redis Cache / Broker)]
        MinIO[(☁️ MinIO / S3 Documentos)]
        N8N[🤖 n8n Workflows - IA / Chat]
        D365[💼 Dynamics 365 ERP - Requisiciones]
    end

    Web --> Django
    Mobile --> Django

    Django --> Postgres
    Django --> Redis
    Django --> MinIO
    
    Celery --> Redis
    Celery --> Postgres
    Celery --> MinIO
    
    CeleryBeat --> Redis
    
    Django -.-> N8N
    Django -.-> D365
```

## 🛠️ Tecnologías Utilizadas

1. **Backend**: Python 3 con Django.
2. **Base de Datos**: PostgreSQL para almacenamiento relacional transaccional.
3. **Almacenamiento de Archivos (Object Storage)**: MinIO (compatible con AWS S3) para archivos PDF de manuales, planos, evidencias y firmas electrónicas.
4. **Broker / Caché**: Redis para comunicación de Celery y caché de consultas de rendimiento del dashboard.
5. **Tareas en Segundo Plano**: Celery para importación asíncrona de activos, ubicaciones, materiales y rutinas.
6. **Automatización e IA**: n8n para flujos inteligentes, vectorización y consultas en lenguaje natural a documentos técnicos.
7. **ERP Corporativo**: Microsoft Dynamics 365 para sincronización bidireccional de presupuestos y requisiciones.
8. **Orquestación**: Docker, Docker Compose y Coolify para despliegue continuo automatizado.

---
🔙 Volver a [[00_Inicio|Inicio]]
"""
    with open(os.path.join(VAULT_DIR, '01_Arquitectura', 'Arquitectura_General.md'), 'w', encoding='utf-8') as f:
        f.write(arq_content)

    # 3. 01_Arquitectura/Base_de_Datos.md
    db_content = """# 🗄️ Base de Datos y Relaciones Core

La base de datos de **Energy** es una base relacional robusta en PostgreSQL. Los modelos de datos se conectan entre sí para dar soporte completo a la operación industrial.

## 🗺️ Diagrama de Relaciones de Negocio (ERD Simplificado)

El siguiente diagrama ilustra cómo interactúan los diferentes módulos de negocio en la base de datos:

```mermaid
erDiagram
    UBICACION ||--o{ ACTIVO : "contiene"
    ACTIVO ||--o{ ORDEN_TRABAJO : "tiene"
    ORDEN_TRABAJO ||--o{ VALOR_PASO_ORDEN : "registra checklist"
    ORDEN_TRABAJO ||--o{ CIERRE_ORDEN_TRABAJO : "se cierra con"
    RUTINA ||--o{ PROGRAMACION : "se programa con"
    PROGRAMACION ||--o{ ORDEN_TRABAJO : "genera automáticamente"
    ACTIVO ||--o{ PUNTO_MEDICION : "mide"
    PUNTO_MEDICION ||--o{ DOCUMENTO_MEDICION : "registra"
    
    ACTIVO ||--o{ BIEN_AFECTO : "se asegura en"
    
    REQUISICION ||--o{ ARTICULO_REQUISICION : "contiene"
    PARTIDA_PRESUPUESTARIA ||--o{ REQUISICION : "financia"
    PARTIDA_PRESUPUESTARIA ||--o{ COMPROMISO : "afecta"
    
    PERMISO_TRABAJO ||--o{ VERIFICACION_REQUISITO : "valida"
    ORDEN_TRABAJO ||--o{ PERMISO_TRABAJO : "requiere"
    
    DOCUMENTO ||--o{ REVISION : "tiene historial"
    DOCUMENTO ||--o{ COMENTARIO_DOCUMENTO : "recibe comentarios/pines"
```

## 🔄 Integridad Referencial y Buenas Prácticas

1. **Índices y Desempeño**: Las consultas sobre el explorador jerárquico de activos y las ubicaciones utilizan anotaciones SQL optimizadas para evitar problemas de N+1 (consultas recursivas lentas).
2. **Soft Deletes**: Los modelos críticos implementan marcas de estado en lugar de eliminación física directa, lo que garantiza la trazabilidad histórica de las órdenes de trabajo y presupuestos.
3. **Auditoría**: Tablas clave tienen campos `creado_por`, `creado_en`, `modificado_por` y `modificado_en`.
4. **Integración Dynamics**: Las requisiciones importadas de Dynamics 365 mantienen su clave externa única (`folio`), lo que permite actualizaciones incrementales seguras.

---
🔙 Volver a [[00_Inicio|Inicio]]
"""
    with open(os.path.join(VAULT_DIR, '01_Arquitectura', 'Base_de_Datos.md'), 'w', encoding='utf-8') as f:
        f.write(db_content)

    # 4. 01_Arquitectura/Servicios_y_Sistemas_Externos.md
    ext_content = """# ☁️ Servicios y Sistemas Externos

El poder de **Energy** radica en su capacidad de orquestar servicios de terceros para ofrecer una experiencia industrial conectada.

## 🗂️ 1. MinIO / Almacenamiento S3
- **Propósito**: Repositorio seguro para archivos cargados en el módulo de documentos (planos, PDFs, manuales técnicos) e imágenes adjuntas a órdenes de trabajo y auditorías.
- **Funcionamiento**: Django se comunica mediante `django-storages` y la API compatible con Amazon S3. 
- **Ventaja**: Permite almacenar terabytes de datos técnicos sin ocupar espacio en el disco del servidor de base de datos.
- **Trazabilidad**: Las revisiones de documentos apuntan al almacenamiento remoto, manteniendo la versión exacta firmada digitalmente.

## 🤖 2. n8n (Inteligencia Artificial y Workflows)
- **Propósito**: Ejecución de flujos lógicos automáticos y asistente de IA.
- **Flujos**:
  - **Vectorización de Documentos**: Los PDFs técnicos se procesan a través de un flujo en n8n para extraer texto y generar embeddings vectoriales.
  - **Chat de IA**: Permite a los técnicos chatear con los manuales técnicos del activo en campo a través de un chat en la app móvil.
- **Configuración**: Comunicación vía Webhooks seguros entre Django y el servidor n8n.

## ⚙️ 3. Celery y Redis (Procesamiento Asíncrono)
- **Propósito**: Ejecución de tareas pesadas fuera de la solicitud HTTP (importaciones de catálogos de 80,000+ activos, generación de reportes anuales, envío masivo de correos).
- **Broker**: Redis actúa como broker de mensajería rápido.
- **Workers**: Workers distribuidos de Celery que procesan tareas fila por fila, enviando actualizaciones de progreso en tiempo real usando caché para polling en la UI.

## 💼 4. Microsoft Dynamics 365 (ERP)
- **Propósito**: Sincronización de transacciones financieras y estados de compras.
- **Flujo**: Sincronización asíncrona de Requisiciones, Presupuestos y Partidas, asegurando que la operación de mantenimiento no exceda el presupuesto disponible en el ERP corporativo.

---
🔙 Volver a [[00_Inicio|Inicio]]
"""
    with open(os.path.join(VAULT_DIR, '01_Arquitectura', 'Servicios_y_Sistemas_Externos.md'), 'w', encoding='utf-8') as f:
        f.write(ext_content)

    # 5. 03_Flujos_y_Procesos/Conexion_DB_Remota.md
    tunnel_content = """# 🔌 Conexión Remota a Base de Datos en VM

Este procedimiento detalla cómo conectar un entorno local de Django a la base de datos PostgreSQL que corre dentro de una Máquina Virtual (VirtualBox/Coolify) alojada en un servidor físico remoto de la planta.

## 📋 1. Preparación en la Máquina Virtual (Destino Final)
Asegurarse de que Postgres acepte conexiones externas y tenga las credenciales correctas.
- **Puerto predeterminado**: `5432`
- **Comando para forzar contraseña de administración**:
  ```bash
  docker exec -it [CONTAINER_ID] psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'clave_elegida';"
  ```
- **Verificar la IP interna de la VM**: `hostname -I` (por ejemplo: `10.30.1.11`)

## 🖥️ 2. Configuración en la Máquina Física (Servidor Intermedio)
Si la VM está en modo NAT o detrás de una IP física corporativa, se debe mapear el puerto usando `netsh` en Windows desde una terminal como Administrador:
```powershell
netsh interface portproxy add v4tov4 listenport=5433 listenaddress=0.0.0.0 connectport=5432 connectaddress=10.30.1.11
```
> [!WARNING]
> **Conflicto de Puertos**: Asegúrate de detener el servicio local de PostgreSQL en el servidor intermedio si este ya está utilizando el puerto mapeado.

## 💻 3. Acceso desde la Computadora de Desarrollo (Local)
Para máxima estabilidad y seguridad, abrimos un túnel SSH seguro desde tu laptop local de desarrollo:
```powershell
ssh -p [PUERTO_SSH] -L 5433:localhost:5432 [USER]@[IP_PUBLICA]
```

## ⚙️ 4. Configuración en Django (settings.py)
Asegura que el entorno local use el puerto del túnel y que la variable `DATABASE_URL` del archivo `.env` no interfiera:

```python
if os.environ.get('DATABASE_URL'):
    # Producción
    DATABASES = {'default': dj_database_url.config(...)}
else:
    # Desarrollo Local con Túnel SSH
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': '127.0.0.1',
            'PORT': '5433',
            'NAME': 'postgres',
            'USER': 'postgres',
            'PASSWORD': 'clave_elegida',
            'OPTIONS': {'sslmode': 'disable'},
        }
    }
```

---
🔙 Volver a [[00_Inicio|Inicio]]
"""
    with open(os.path.join(VAULT_DIR, '03_Flujos_y_Procesos', 'Conexion_DB_Remota.md'), 'w', encoding='utf-8') as f:
        f.write(tunnel_content)

    # 6. 03_Flujos_y_Procesos/Importacion_Asincrona_Celery.md
    celery_content = """# 📥 Importaciones Masivas Asíncronas (Celery & Redis)

El sistema **Energy** maneja grandes catálogos (más de 80,000 activos y repuestos). Para evitar tiempos de espera y caídas por timeout en el servidor web HTTP, implementamos un flujo de importación asíncrono robusto.

## 🗺️ Diagrama del Flujo de Trabajo

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario (Navegador)
    participant DJ as Django Web Server
    participant RD as Redis Cache & Broker
    participant CW as Celery Worker
    participant DB as PostgreSQL

    U->>DJ: Sube archivo Excel/CSV (Importar)
    DJ->>DJ: Guarda archivo temporal y valida cabeceras
    DJ->>RD: Registra ID de tarea e inicia en segundo plano
    DJ-->>U: Retorna Task ID (Respuesta HTTP inmediata)
    U->>DJ: Polling AJAX (Cada 1s pide progreso)
    
    activate CW
    RD->>CW: Ejecuta mi_tarea_importacion(file_path)
    loop Fila por Fila
        CW->>CW: Carga fila usando ModelInstanceLoader
        CW->>DB: Realiza import_row (Verifica duplicados / Guarda)
        CW->>RD: Actualiza Caché con % de progreso y errores
        DJ->>RD: Obtiene estado actual de la Caché
        DJ-->>U: Retorna progreso en tiempo real
    end
    CW->>RD: Marca tarea como COMPLETED
    deactivate CW
    
    DJ-->>U: Muestra SweetAlert2 de éxito e historial de logs
```

## ⚙️ 1. Configuración del Worker (Windows)
En entornos de desarrollo en Windows, Celery requiere el pool de hilos `eventlet` o `gevent` para funcionar correctamente.
1. **Ejecutar comando del worker**:
   ```powershell
   celery -A energia worker -l info -P eventlet
   ```
2. **Configuración de Variables de Entorno (.env)**:
   - `CELERY_BROKER_URL = 'redis://localhost:6379/0'`
   - `CELERY_RESULT_BACKEND = 'django-db'`

## 📝 2. Patrón de Tareas (`tasks.py`)
Para mostrar progreso fluido en la interfaz gráfica (UI), la tarea procesa iterativamente utilizando el cargador compatible con django-import-export:

```python
from import_export.instance_loaders import ModelInstanceLoader
from celery import shared_task

@shared_task(bind=True)
def tarea_importar_activos(self, file_path, file_format, user_id=None):
    from django.core.files.storage import default_storage
    from .admin import ActivoResource
    
    resource = ActivoResource()
    with default_storage.open(file_path, 'rb') as f:
        # Cargar datos en dataset usando tablib...
        
    for i, row in enumerate(dataset.dict, start=1):
        # 1. Obtener cargador de instancias para evitar duplicados
        instance_loader = ModelInstanceLoader(resource, dataset)
        
        # 2. Importar fila individualmente con el número de fila obligatorio
        row_result = resource.import_row(row, instance_loader, row_number=i, dry_run=False)
        
        # 3. Notificar progreso a Celery y guardar estado en Redis
        self.update_state(state='PROGRESS', meta={
            'current': i,
            'total': total,
            'percent': int((i / total) * 100)
        })
```

## 🎨 3. Interfaz de Usuario y UX Premium
- **Glassmorphism**: La barra de progreso y el panel de logs usan estilos premium (`backdrop-filter: blur(12px)`) para integrarse al diseño visual del sistema.
- **Manejo de Errores**: Si ocurre un error en una fila, la importación no se detiene; se registra el error en una lista en caché y se renderiza en la consola de logs en tiempo real para que el usuario pueda corregirlo posteriormente.

---
🔙 Volver a [[00_Inicio|Inicio]]
"""
    with open(os.path.join(VAULT_DIR, '03_Flujos_y_Procesos', 'Importacion_Asincrona_Celery.md'), 'w', encoding='utf-8') as f:
        f.write(celery_content)

    # 7. 03_Flujos_y_Procesos/Wizard_Seguridad_AST.md
    wizard_content = """# 🛡️ Wizard de Permisos de Trabajo & AST

El Análisis de Seguridad en el Trabajo (AST) es obligatorio para realizar mantenimientos críticos en la planta. Para simplificar esta tarea, se diseñó un **Wizard Multiaso dinámico** integrado en el módulo de seguridad.

## 🗺️ Diagrama del Flujo del Permiso de Trabajo

```mermaid
graph TD
    classDef step fill:#1e1e2e,stroke:#f5c2e7,stroke-width:1px,color:#cdd6f4;
    classDef approved fill:#a6e3a1,stroke:#a6e3a1,stroke-width:1px,color:#11111b;

    S1[Paso 1: Información General y Activo] --> S2[Paso 2: Identificar Riesgos]
    S2 --> S3[Paso 3: Definir Controles de Mitigación]
    S3 --> S4[Paso 4: Asignar Requisitos de Permiso]
    S4 --> S5[Paso 5: Firmas y Envío]
    
    S5 --> APROV{Flujo de Aprobación}
    
    APROV -->|Firma Supervisor| A[Habilitado / Permiso Activo]
    APROV -->|Rechazado| R[Borrador / Requiere Edición]
    
    class S1,S2,S3,S4,S5 step;
    class A approved;
```

## ⚙️ Características Técnicas

1. **Persistencia del Borrador**: Los pasos del formulario se envían y persisten asíncronamente en el modelo `PermisoTrabajo` con el estado `BORRADOR`. Si el técnico en campo pierde la conexión, la información no se pierde.
2. **Catálogos Dinámicos**: Los riesgos y sus controles correspondientes se cargan automáticamente desde los catálogos estandarizados (`Riesgo` y `Control`) en base al tipo de actividad, evitando la digitación manual y errores ortográficos.
3. **Firmas Digitales Cruzadas**: El sistema requiere la firma digital electrónica del técnico ejecutor y la del supervisor responsable. Las firmas se validan mediante perfiles encriptados y se plasman en el documento PDF final guardado en MinIO.
4. **Validación Bypass en Cliente**: Para garantizar la resiliencia en dispositivos móviles, se implementó validación personalizada por paso en JavaScript, evitando conflictos con validaciones nativas de HTML5 en navegadores móviles integrados.

---
🔙 Volver a [[00_Inicio|Inicio]]
"""
    with open(os.path.join(VAULT_DIR, '03_Flujos_y_Procesos', 'Wizard_Seguridad_AST.md'), 'w', encoding='utf-8') as f:
        f.write(wizard_content)

    # 8. 04_Operaciones/Instalacion_Local.md
    inst_content = """# 💻 Instalación y Configuración Local

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
.\\env\\Scripts\\activate
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
"""
    with open(os.path.join(VAULT_DIR, '04_Operaciones', 'Instalacion_Local.md'), 'w', encoding='utf-8') as f:
        f.write(inst_content)

    # 9. 04_Operaciones/Despliegue_Coolify.md
    coolify_content = """# 🚀 Especificaciones de Despliegue en Coolify / Docker

El ecosistema **Energy** se despliega de manera automatizada utilizando **Coolify**, permitiendo despliegues continuos y controlados con Docker.

## 🏗️ Dockerfile del Ecosistema
El despliegue utiliza una imagen base oficial de Python. Los servicios web y workers comparten la misma imagen Docker, ejecutando diferentes comandos según la configuración de Coolify.

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \\
    build-essential \\
    libpq-dev \\
    python3-dev \\
    git \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Comando por defecto para el web server
CMD ["gunicorn", "energia.wsgi:application", "--bind", "0.0.0.0:8000"]
```

## 📋 Configuración en Coolify

En el dashboard de Coolify, el ecosistema se configura mediante un archivo `docker-compose.yml` multi-contenedor:

1. **`web`**: Servicio Django que sirve las solicitudes HTTP mediante Gunicorn en el puerto `8000`.
2. **`worker`**: Worker de Celery para tareas asíncronas pesadas (se ejecuta sin mapear puertos, con comando `celery -A energia worker -l info`).
3. **`beat`**: Planificador Celery Beat para rutinas periódicas de mantenimiento.
4. **`redis`**: Contenedor oficial de Redis como Broker de mensajería rápido.
5. **`postgres`**: Contenedor de PostgreSQL para la base de datos persistente.
6. **`minio`**: Object Storage para almacenamiento de archivos PDFs y planos.

## 🛡️ Variables de Entorno en Producción (Configuradas en Coolify)
- `DEBUG=False`
- `SECRET_KEY=<clave_segura_produccion>`
- `DATABASE_URL=postgres://user:password@postgres:5432/dbname`
- `CELERY_BROKER_URL=redis://redis:6379/0`
- `AWS_ACCESS_KEY_ID=<minio_user>`
- `AWS_SECRET_ACCESS_KEY=<minio_password>`
- `AWS_STORAGE_BUCKET_NAME=energy-docs`
- `AWS_S3_ENDPOINT_URL=http://minio:9000`

---
🔙 Volver a [[00_Inicio|Inicio]]
"""
    with open(os.path.join(VAULT_DIR, '04_Operaciones', 'Despliegue_Coolify.md'), 'w', encoding='utf-8') as f:
        f.write(coolify_content)

    print("Curated guides and architecture documents written to Obsidian Vault.")

def dump_django_models():
    """Scan Django registered apps and automatically generate Obsidian pages for each local app"""
    print("Scanning Django models and generating Obsidian notes...")
    
    for app_label in LOCAL_APPS:
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            print(f"Skipping {app_label}: app not registered in settings.")
            continue
            
        app_title = APP_NAMES.get(app_label, app_label.capitalize())
        models_list = app_config.get_models()
        
        md_content = []
        md_content.append(f"# 📂 Módulo: {app_title} (`{app_label}`)\n")
        
        # Add metadata / tags
        md_content.append(f"> [!INFO]")
        md_content.append(f"> **Etiquetas**: #django/app #{app_label} ")
        md_content.append(f"> **Propósito**: {app_config.verbose_name or app_title}")
        md_content.append(f"> **Ubicación en Código**: `file:///d:/Apps/energia/energy/{app_label}`\n")
        
        md_content.append("---\n")
        md_content.append("## 📦 Modelos de Datos (Base de Datos)\n")
        md_content.append(f"Este módulo gestiona los siguientes modelos en la base de datos. Los campos ForeignKey y relaciones ManyToMany se representan con enlaces `[[ModelName]]` para navegar interactivamente en Obsidian.\n")
        
        models_count = 0
        for model in models_list:
            models_count += 1
            model_name = model.__name__
            model_doc = model.__doc__ or "Sin descripción disponible."
            # Clean up default django docstrings
            if f"{model_name}(" in model_doc:
                model_doc = "Modelo maestro del sistema."
                
            md_content.append(f"### 🗂️ Modelo `[[{model_name}]]`\n")
            md_content.append(f"> **Descripción**: {model_doc.strip()}\n")
            
            # Fields table
            md_content.append("| Campo | Tipo de Dato | Relación / Enlace | Descripción / Verbose Name |")
            md_content.append("| :--- | :--- | :--- | :--- |")
            
            # Get regular fields, ForeignKeys and ManyToManyFields
            model_fields = list(model._meta.fields) + list(model._meta.many_to_many)
            for field in model_fields:
                
                field_name = field.name
                field_type = field.get_internal_type() if hasattr(field, 'get_internal_type') else type(field).__name__
                
                # Check relations
                relation_link = "-"
                if field.is_relation and field.related_model:
                    rel_model_name = field.related_model.__name__
                    relation_link = f"`{field_type}` ➡️ [[{rel_model_name}]]"
                
                # Description / verbose name
                verbose = getattr(field, 'verbose_name', '-')
                help_text = getattr(field, 'help_text', '')
                desc = str(verbose)
                if help_text:
                    desc += f" ({help_text})"
                
                md_content.append(f"| `{field_name}` | `{field_type}` | {relation_link} | {desc} |")
                
            md_content.append("\n")
            
        if models_count == 0:
            md_content.append("> *Este módulo no registra modelos directos en base de datos. Actúa principalmente como módulo de lógica, vistas o integraciones.*")
            
        md_content.append("\n---\n🔙 Volver a [[00_Inicio|Inicio]]")
        
        # Write module file
        file_path = os.path.join(VAULT_DIR, '02_Modulos', f"{app_label.capitalize()}.md")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_content))
            
        print(f"Generated module documentation: {file_path}")

    # Generate single model placeholder files so Obsidian linking works perfectly!
    print("Generating model shortcut placeholder notes for Obsidian Graph...")
    model_placeholders_dir = os.path.join(VAULT_DIR, '02_Modulos', 'Modelos_Detalle')
    os.makedirs(model_placeholders_dir, exist_ok=True)
    
    for app_label in LOCAL_APPS:
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            continue
            
        for model in app_config.get_models():
            model_name = model.__name__
            model_doc = model.__doc__ or "Modelo de datos del ecosistema Energy."
            if f"{model_name}(" in model_doc:
                model_doc = "Modelo de datos del ecosistema Energy."
                
            placeholder_content = f"""# Model: {model_name}

#django/model #{model_label_tag(app_label)}

## Descripción
{model_doc.strip()}

## Módulo Contenedor
Pertenece al módulo: [[{app_label.capitalize()}]]

---
🔙 Volver a [[00_Inicio|Inicio]]
"""
            with open(os.path.join(model_placeholders_dir, f"{model_name}.md"), 'w', encoding='utf-8') as f:
                f.write(placeholder_content)

def model_label_tag(app):
    return app.lower()

if __name__ == '__main__':
    create_directories()
    generate_static_files()
    dump_django_models()
    print("\nSUCCESS: Obsidian Vault successfully generated at:")
    print(os.path.join(os.getcwd(), 'docs', 'obsidian_vault'))
    print("You can now open this folder directly in Obsidian as a Vault!")
