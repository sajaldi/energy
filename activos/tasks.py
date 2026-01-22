from celery import shared_task
from import_export import resources
from .models import Ubicacion, Activo, Plano
from .admin import UbicacionResource, ActivoResource
import time

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
    
    # Inicializar el resource
    resource = UbicacionResource()
    
    # Leer el archivo
    with open(file_path, 'rb') as f:
        if file_format == 'csv':
            dataset = Dataset().load(f.read().decode('utf-8'), format='csv')
        elif file_format in ['xls', 'xlsx']:
            dataset = Dataset().load(f.read(), format=file_format)
        else:
            raise ValueError(f"Formato no soportado: {file_format}")
    
    total_rows = len(dataset)
    
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
            
            # Procesar la fila
            instance_loader = resources.InstanceLoader(resource, dataset)
            row_result = resource.import_row(
                row,
                instance_loader,
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
        os.remove(file_path)
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
    
    resource = ActivoResource()
    
    # Leer el archivo
    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()
            if file_format == 'csv':
                dataset = Dataset().load(file_content.decode('utf-8', errors='ignore'), format='csv')
            elif file_format in ['xls', 'xlsx']:
                dataset = Dataset().load(file_content, format=file_format)
            else:
                raise ValueError(f"Formato no soportado: {file_format}")
    except Exception as e:
        registro.estado = 'ERROR'
        registro.detalles_error = f"Error al leer archivo: {str(e)}"
        registro.save()
        return {'status': 'error', 'message': str(e)}

    total_rows = len(dataset)
    registro.total_rows = total_rows
    registro.save()
    
    # Marcador de progreso en caché para la UI compatible con el frontend actual
    cache_key = f"import_progress_{user_id}" if user_id else "import_progress_system"
    cache.set(cache_key, {'current': 0, 'total': total_rows, 'status': 'Iniciando...'}, 3600)

    self.update_state(
        state='PROGRESS',
        meta={'current': 0, 'total': total_rows, 'status': 'Cargando datos...'}
    )
    
    result = resource.import_data(dataset, dry_run=False, raise_errors=False, user=user)
    
    # Recoger IDs creados desde el resource
    ids_creados = getattr(resource, '_ids_creados', [])
    
    # Finalizar registro
    registro.filas_nuevas = result.totals.get('new', 0)
    registro.filas_actualizadas = result.totals.get('update', 0)
    registro.filas_omitidas = result.totals.get('skip', 0)
    registro.filas_error = len(result.row_errors())
    registro.ids_creados = json.dumps(ids_creados)
    registro.estado = 'COMPLETADO'
    registro.save()

    # Limpiar
    if os.path.exists(file_path):
        os.remove(file_path)
    
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
    """
    Tarea Celery para importar PLANOS con seguimiento de progreso real.
    """
    from tablib import Dataset
    import os
    from .admin import PlanoResource
    
    # Inicializar resource
    resource = PlanoResource()
    
    # Leer archivo
    try:
        with open(file_path, 'rb') as f:
            if file_format == 'csv':
                dataset = Dataset().load(f.read().decode('utf-8', errors='ignore'), format='csv')
            elif file_format in ['xls', 'xlsx']:
                dataset = Dataset().load(f.read(), format=file_format)
            else:
                raise ValueError(f"Formato no soportado: {file_format}")
    except FileNotFoundError:
        return {'status': 'error', 'message': 'Archivo temporal no encontrado'}

    total_rows = len(dataset)
    
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
            
            # Importar fila
            instance_loader = resources.InstanceLoader(resource, dataset)
            row_result = resource.import_row(row, instance_loader, dry_run=False)
            result.append_row_result(row_result)
            
        except Exception as e:
            result.append_base_error(resources.Error(error=e, traceback=str(e), row=row))
            
    # Limpiar archivo
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
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
