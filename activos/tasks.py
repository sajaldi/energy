from celery import shared_task
from import_export import resources
from .models import Ubicacion, Activo, Plano
import time

def try_decode(content, encodings=['utf-8-sig', 'iso-8859-1', 'windows-1252', 'utf-8']):
    """Intenta decodificar el contenido usando una lista de encodings prioritarios."""
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Si ninguno funciona, forzar utf-8 ignorando errores para que al menos no rompa la tarea
    return content.decode('utf-8', errors='ignore')

@shared_task(bind=True)
def import_ubicaciones_task(self, file_path, file_format):
    """
    Tarea Celery para importar ubicaciones con seguimiento de progreso.
    
    Args:
        self: Instancia de la tarea (bind=True)
        file_path: Ruta al archivo temporal de importación
        file_format: Formato del archivo ('csv', 'xlsx', etc.)
    
    Returns:
        dict: Resultado de la importación con estadísticas
    """
    from tablib import Dataset
    import os
    
    # Inicializar el resource y cachés
    from .admin import UbicacionResource
    resource = UbicacionResource()
    
    from django.core.files.storage import default_storage
    # Leer el archivo
    with default_storage.open(file_path, 'rb') as f:
        file_content = f.read()
        if file_format == 'csv':
            dataset = Dataset().load(try_decode(file_content), format='csv')
        elif file_format in ['xls', 'xlsx']:
            dataset = Dataset().load(file_content, format=file_format)
        else:
            raise ValueError(f"Formato no soportado: {file_format}")
    
    total_rows = len(dataset)
    resource.before_import(dataset)
    
    # Actualizar estado inicial
    self.update_state(
        state='PROGRESS',
        meta={
            'current': 0,
            'total': total_rows,
            'status': 'Iniciando importación...',
            'current_row': None
        }
    )
    
    # Procesar fila por fila con seguimiento
    result = resources.Result()
    for i, row in enumerate(dataset.dict, start=1):
        try:
            # Obtener nombre de la fila para mostrar
            row_name = row.get('nombre', f'Fila {i}')
            
            # Actualizar progreso
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': i,
                    'total': total_rows,
                    'status': f'Procesando {i}/{total_rows}',
                    'current_row': row_name,
                    'percent': int((i / total_rows) * 100)
                }
            )
            
            # Procesar la fila (usando ModelInstanceLoader para IE 4.x)
            from import_export.instance_loaders import ModelInstanceLoader
            instance_loader = ModelInstanceLoader(resource, dataset)
            row_result = resource.import_row(
                row,
                instance_loader,
                row_number=i,
                dry_run=False
            )
            result.append_row_result(row_result)
            
        except Exception as e:
            # Registrar error pero continuar
            result.append_base_error(
                resources.Error(
                    error=e,
                    traceback=str(e),
                    row=row
                )
            )
    
    # Limpiar archivo temporal
    try:
        if default_storage.exists(file_path):
            default_storage.delete(file_path)
    except:
        pass
    
    # Retornar resultado final
    return {
        'status': 'completed',
        'total': total_rows,
        'new': result.totals.get('new', 0),
        'updated': result.totals.get('update', 0),
        'skipped': result.totals.get('skip', 0),
        'errors': len(result.base_errors) + len(result.row_errors()),
        'error_messages': [str(e.error) for e in result.base_errors[:10]]  # Primeros 10 errores
    }

@shared_task(bind=True)
def import_activos_task(self, file_path, file_format, user_id=None, import_name="Importación sin nombre"):
    """
    Tarea Celery para importar activos con seguimiento de progreso y reversión.
    """
    from tablib import Dataset
    import os
    import json
    from django.contrib.auth.models import User
    from django.core.cache import cache
    from .models import RegistroImportacion
    
    user = User.objects.get(id=user_id) if user_id else None
    
    # Crear registro de importación
    registro = RegistroImportacion.objects.create(
        nombre=import_name,
        usuario=user,
        estado='PROCESANDO'
    )
    
    from .admin import ActivoResource
    resource = ActivoResource()
    
    from django.core.files.storage import default_storage
    # Leer el archivo
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
        registro.estado = 'ERROR'
        registro.detalles_error = f"Error al leer archivo: {str(e)}"
        registro.save()
        return {'status': 'error', 'message': str(e)}

    # Configurar el resource y cachés
    from .admin import ActivoResource
    from import_export import resources
    resource = ActivoResource()
    
    total_rows = len(dataset)
    registro.total_rows = total_rows
    registro.save()
    
    # Inicializar cachés (crítico para evitar AttributeError: activo_id_cache)
    resource.before_import(dataset, user=user)
    
    # Marcador de progreso en caché para la UI compatible con el frontend
    cache_key = f"import_progress_{user_id}" if user_id else "import_progress_system"
    
    ids_creados = []
    
    # Procesar fila por fila para ver progreso real
    for i, row in enumerate(dataset.dict, start=1):
        try:
            # Feedback cada 5 filas para fluidez
            if i % 5 == 0 or i == total_rows:
                progress_info = {
                    'current': i, 
                    'total': total_rows, 
                    'status': f'Procesando activo {i}/{total_rows}: {row.get("nombre", "")}', 
                    'percent': int((i / total_rows) * 100),
                    'new': registro.filas_nuevas,
                    'updated': registro.filas_actualizadas,
                    'skipped': registro.filas_omitidas,
                    'errors': registro.filas_error,
                    'last_log': f'Procesado: {row.get("nombre", "S/N")}',
                }
                if hasattr(self, '_last_error_tmp'):
                    progress_info['last_error'] = self._last_error_tmp
                    del self._last_error_tmp

                cache.set(cache_key, progress_info, 3600)
                # Actualizar estado de Celery también
                self.update_state(state='PROGRESS', meta=progress_info)

            # Obtener el cargador de instancias correcto (ModelInstanceLoader en IE 4.x)
            from import_export.instance_loaders import ModelInstanceLoader
            instance_loader = ModelInstanceLoader(resource, dataset)
            
            # Procesar la fila pasando el número de fila (requerido en IE 4.x)
            row_result = resource.import_row(row, instance_loader, row_number=i, dry_run=False)
            
            if row_result.import_type == resources.RowResult.IMPORT_TYPE_NEW:
                registro.filas_nuevas += 1
                if row_result.object_id:
                    ids_creados.append(row_result.object_id)
            elif row_result.import_type == resources.RowResult.IMPORT_TYPE_UPDATE:
                registro.filas_actualizadas += 1
            elif row_result.import_type == resources.RowResult.IMPORT_TYPE_SKIP:
                registro.filas_omitidas += 1
            
            if row_result.errors:
                registro.filas_error += len(row_result.errors)
                err_text = "; ".join([str(e.error) for e in row_result.errors])
                self._last_error_tmp = f"Fila {i} ({row.get('nombre')}): {err_text}"

        except Exception as e:
            registro.filas_error += 1
            error_msg = f"Error en fila {i}: {str(e)}"
            self._last_error_tmp = error_msg
            registro.detalles_error = (registro.detalles_error or "") + error_msg + "\n"
            
        if i % 100 == 0:
            registro.save()

    # Guardar resultados finales en el registro
    registro.ids_creados = json.dumps(ids_creados)
    registro.estado = 'COMPLETADO'
    registro.save()

    # Limpiar archivo temporal
    try:
        from django.core.files.storage import default_storage
        if default_storage.exists(file_path):
            default_storage.delete(file_path)
    except:
        pass
    
    final_res = {
        'status': 'completed',
        'registro_id': registro.id,
        'total': total_rows,
        'new': registro.filas_nuevas,
        'updated': registro.filas_actualizadas,
        'skipped': registro.filas_omitidas,
        'errors': registro.filas_error,
    }
    cache.set(cache_key, final_res, 3600)
    return final_res

@shared_task(bind=True)
def revertir_importacion_task(self, registro_id):
    """
    Tarea para eliminar los activos creados en una importación específica.
    """
    from .models import RegistroImportacion, Activo
    import json
    
    try:
        registro = RegistroImportacion.objects.get(id=registro_id)
        if registro.estado != 'COMPLETADO':
            return {'status': 'error', 'message': 'Solo se pueden revertir importaciones completadas.'}
        
        ids = json.loads(registro.ids_creados) if registro.ids_creados else []
        if not ids:
            registro.estado = 'REVERTIDO'
            registro.save()
            return {'status': 'completed', 'message': 'No había activos nuevos para eliminar.'}
        
        total = len(ids)
        # Eliminar activos por ID
        # Usamos filter().delete() para mayor eficiencia
        borrados, _ = Activo.objects.filter(id__in=ids).delete()
        
        registro.estado = 'REVERTIDO'
        registro.save()
        
        return {'status': 'completed', 'deleted_count': borrados, 'expected_count': total}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
@shared_task(bind=True)
def import_planos_task(self, file_path, file_format):
    """
    Tarea Celery para importar PLANOS con seguimiento de progreso real.
    """
    from tablib import Dataset
    import os
    from .admin import PlanoResource
    
    # Inicializar resource
    resource = PlanoResource()
    
    from django.core.files.storage import default_storage
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
    except FileNotFoundError:
        return {'status': 'error', 'message': 'Archivo temporal no encontrado'}

    total_rows = len(dataset)
    resource.before_import(dataset)
    
    # Estado inicial
    self.update_state(
        state='PROGRESS',
        meta={'current': 0, 'total': total_rows, 'status': 'Iniciando importación...', 'percent': 0}
    )
    
    result = resources.Result()
    
    for i, row in enumerate(dataset.dict, start=1):
        try:
            # Feedback en Redis cada 5 filas para que la barra se mueva fluido
            if i % 5 == 0 or i == total_rows:
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i, 
                        'total': total_rows, 
                        'status': f'Procesando plano {i}/{total_rows}: {row.get("nombre", "")}', 
                        'percent': int((i / total_rows) * 100)
                    }
                )
            
            # Importar fila (usando ModelInstanceLoader para IE 4.x)
            from import_export.instance_loaders import ModelInstanceLoader
            instance_loader = ModelInstanceLoader(resource, dataset)
            row_result = resource.import_row(row, instance_loader, row_number=i, dry_run=False)
            result.append_row_result(row_result)
            
        except Exception as e:
            result.append_base_error(resources.Error(error=e, traceback=str(e), row=row))
            
    # Limpiar archivo
    try:
        from django.core.files.storage import default_storage
        if default_storage.exists(file_path):
            default_storage.delete(file_path)
    except:
        pass
        
    return {
        'status': 'completed',
        'total': total_rows,
        'new': result.totals.get('new', 0),
        'updated': result.totals.get('update', 0),
        'skipped': result.totals.get('skip', 0),
        'errors': len(result.base_errors) + len(result.row_errors()),
    }
