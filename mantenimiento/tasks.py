from celery import shared_task
from import_export import resources
from .models import Rutina
import time
import os

def try_decode(content, encodings=['utf-8-sig', 'iso-8859-1', 'windows-1252', 'utf-8']):
    """Intenta decodificar el contenido usando una lista de encodings prioritarios."""
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Si ninguno funciona, forzar utf-8 ignorando errores
    return content.decode('utf-8', errors='ignore')

@shared_task(bind=True)
def import_rutinas_task(self, file_path, file_format, user_id=None):
    """
    Tarea Celery para importar RUTINAS con seguimiento de progreso real.
    """
    from tablib import Dataset
    from django.core.files.storage import default_storage
    from .admin import RutinaResource
    from django.core.cache import cache

    # Inicializar resource
    resource = RutinaResource()
    
    # Marcador de progreso en caché
    cache_key = f"import_rutinas_progress_{user_id}" if user_id else "import_rutinas_progress_system"

    # Leer archivo
    try:
        with default_storage.open(file_path, 'rb') as f:
            file_content = f.read()
            if file_format == 'csv':
                dataset = Dataset().load(try_decode(file_content), format='csv')
            elif file_format in ['xls', 'xlsx']:
                dataset = Dataset().load(file_content, format=file_format)
            else:
                raise ValueError(f"Formato no soportado: {file_format}")
    except Exception as e:
        error_res = {'status': 'error', 'message': f'Error al leer archivo: {str(e)}'}
        cache.set(cache_key, error_res, 3600)
        return error_res

    total_rows = len(dataset)
    resource.before_import(dataset)
    
    # Estado inicial
    progress_info = {
        'current': 0, 
        'total': total_rows, 
        'status': 'Iniciando importación...', 
        'percent': 0,
        'new': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0
    }
    cache.set(cache_key, progress_info, 3600)
    self.update_state(state='PROGRESS', meta=progress_info)
    
    result = resources.Result()
    for i, row in enumerate(dataset.dict, start=1):
        try:
            # Feedback en Redis cada 5 filas
            if i % 5 == 0 or i == total_rows:
                progress_info.update({
                    'current': i,
                    'status': f'Procesando rutina {i}/{total_rows}: {row.get("nombre", "")}',
                    'percent': int((i / total_rows) * 100),
                    'new': result.totals.get('new', 0),
                    'updated': result.totals.get('update', 0),
                    'skipped': result.totals.get('skip', 0),
                    'errors': len(result.base_errors) + len(result.row_errors()),
                })
                cache.set(cache_key, progress_info, 3600)
                self.update_state(state='PROGRESS', meta=progress_info)
            
            # Importar fila (usando ModelInstanceLoader para IE 4.x)
            from import_export.instance_loaders import ModelInstanceLoader
            instance_loader = ModelInstanceLoader(resource, dataset)
            row_result = resource.import_row(row, instance_loader, row_number=i, dry_run=False)
            result.append_row_result(row_result)
            
        except Exception as e:
            result.append_base_error(resources.Error(error=e, traceback=str(e), row=row))
            
    # Limpiar archivo
    try:
        if default_storage.exists(file_path):
            default_storage.delete(file_path)
    except:
        pass
        
    final_res = {
        'status': 'completed',
        'total': total_rows,
        'new': result.totals.get('new', 0),
        'updated': result.totals.get('update', 0),
        'skipped': result.totals.get('skip', 0),
        'errors': len(result.base_errors) + len(result.row_errors()),
    }
    cache.set(cache_key, final_res, 3600)
    return final_res
@shared_task(bind=True)
def import_ordenes_task(self, file_path, file_format, user_id=None):
    """
    Tarea Celery para importar ÓRDENES DE TRABAJO con seguimiento de progreso real.
    """
    from tablib import Dataset
    from django.core.files.storage import default_storage
    from .admin import OrdenTrabajoResource
    from django.core.cache import cache

    # Inicializar resource
    resource = OrdenTrabajoResource()
    
    # Marcador de progreso en caché
    cache_key = f"import_ordenes_progress_{user_id}" if user_id else "import_ordenes_progress_system"

    # Leer archivo
    try:
        with default_storage.open(file_path, 'rb') as f:
            file_content = f.read()
            if file_format == 'csv':
                dataset = Dataset().load(try_decode(file_content), format='csv')
            elif file_format in ['xls', 'xlsx']:
                dataset = Dataset().load(file_content, format=file_format)
            else:
                raise ValueError(f"Formato no soportado: {file_format}")
    except Exception as e:
        error_res = {'status': 'error', 'message': f'Error al leer archivo: {str(e)}'}
        cache.set(cache_key, error_res, 3600)
        return error_res

    total_rows = len(dataset)
    resource.before_import(dataset)
    
    # Estado inicial
    progress_info = {
        'current': 0, 
        'total': total_rows, 
        'status': 'Iniciando importación...', 
        'percent': 0,
        'new': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0
    }
    cache.set(cache_key, progress_info, 3600)
    self.update_state(state='PROGRESS', meta=progress_info)
    
    from import_export import resources as ie_resources
    result = ie_resources.Result()
    for i, row in enumerate(dataset.dict, start=1):
        try:
            if i % 5 == 0 or i == total_rows:
                progress_info.update({
                    'current': i,
                    'status': f'Procesando OT {i}/{total_rows}',
                    'percent': int((i / total_rows) * 100),
                    'new': result.totals.get('new', 0),
                    'updated': result.totals.get('update', 0),
                    'skipped': result.totals.get('skip', 0),
                    'errors': len(result.base_errors) + len(result.row_errors()),
                })
                cache.set(cache_key, progress_info, 3600)
                self.update_state(state='PROGRESS', meta=progress_info)
            
            from import_export.instance_loaders import ModelInstanceLoader
            instance_loader = ModelInstanceLoader(resource, dataset)
            row_result = resource.import_row(row, instance_loader, row_number=i, dry_run=False)
            result.append_row_result(row_result)
            
        except Exception as e:
            from import_export import resources as ie_resources
            result.append_base_error(ie_resources.Error(error=e, traceback=str(e), row=row))
            
    # Limpiar archivo
    try:
        if default_storage.exists(file_path):
            default_storage.delete(file_path)
    except:
        pass
        
    final_res = {
        'status': 'completed',
        'total': total_rows,
        'new': result.totals.get('new', 0),
        'updated': result.totals.get('update', 0),
        'skipped': result.totals.get('skip', 0),
        'errors': len(result.base_errors) + len(result.row_errors()),
    }
    cache.set(cache_key, final_res, 3600)
    return final_res
