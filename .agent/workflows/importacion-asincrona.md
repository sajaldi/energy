---
description: Configuración e implementación de importaciones asíncronas masivas con Celery, Redis y django-import-export.
---

Este workflow describe cómo configurar y desarrollar un sistema de importación industrial de alto rendimiento, con seguimiento en tiempo real y manejo robusto de errores.

### 1. Configuración del Entorno (Windows)
1. **Redis**: Asegurarse de que el servicio de Redis esté corriendo localmente.
2. **Dependencias**: Instalar `celery`, `redis`, `django-celery-results`, `django-celery-beat` y `eventlet` (necesario para Windows).
3. **Comando del Worker**: Ejecutar siempre desde el entorno virtual:
   ```powershell
   celery -A energia worker -l info -P eventlet
   ```

### 2. Configuración Core de Celery
- **`energia/celery.py`**: Definir la instancia de `Celery(app_name)`.
- **`energia/__init__.py`**: Importar la app de Celery para que se cargue con Django.
- **`settings.py`**: 
  - `CELERY_BROKER_URL = 'redis://localhost:6379/0'`
  - `CELERY_RESULT_BACKEND = 'django-db'`
  - `CELERY_TASK_TRACK_STARTED = True`

### 3. Implementación de Tareas (`tasks.py`)
Para lograr un progreso fluido en la UI, la tarea debe procesar fila por fila en lugar de usar `resource.import_data()` directamente:

```python
from import_export.instance_loaders import ModelInstanceLoader

@shared_task(bind=True)
def mi_tarea_importacion(self, file_path, file_format, user_id=None):
    from django.core.files.storage import default_storage
    from .admin import MiResource
    
    resource = MiResource()
    with default_storage.open(file_path, 'rb') as f:
        # Cargar dataset con tablib...
        
    for i, row in enumerate(dataset.dict, start=1):
        # 1. Obtener cargador de instancias (IE 4.x compatible)
        instance_loader = ModelInstanceLoader(resource, dataset)
        
        # 2. Importar fila (requiere row_number en IE 4.x)
        row_result = resource.import_row(row, instance_loader, row_number=i, dry_run=False)
        
        # 3. Notificar progreso a Celery y Caché
        self.update_state(state='PROGRESS', meta={'current': i, 'total': total, ...})
```

### 4. Interfaz de Usuario (Templates)
- **Glassmorphism**: Usar `backdrop-filter: blur(12px)` y fondos con opacidad para un look premium.
- **Polling**: Implementar un `setInterval` que consulte el endpoint de status cada 1s.
- **Logs**: Usar un área con scroll automático para mostrar errores en tiempo real conforme lleguen en el JSON de progreso.

### 5. Errores Comunes y Soluciones (Knowledge Base)
- **`AlreadyRegistered`**: Al registrar el Admin de Importación, usar un bloque `try-except admin.site.unregister(Model)` para evitar colisiones si Celery recarga el módulo.
- **`NotImplementedError` (Storage)**: Evitar `default_storage.path()`. Usar siempre rutas relativas y dejar que `default_storage.open()` maneje la localización física (S3 o Local).
- **`row_number`**: La función `import_row` en versiones recientes de `django-import-export` requiere obligatoriamente el argumento `row_number`.
- **`ModelInstanceLoader`**: Es la clase correcta a usar en la versión 4.x para procesar filas individuales manteniendo la lógica de búsqueda de duplicados.

### 6. Funcionalidades de Control
- **Cancelar**: Usar `app.control.revoke(task_id, terminate=True, signal='SIGKILL')` para detener tareas en Windows.
- **Plantilla**: Crear una vista que exporte un `dataset` vacío con las cabeceras del `Resource` para asegurar que el usuario siempre tenga el formato correcto.
