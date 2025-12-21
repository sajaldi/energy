from celery import shared_task
from import_export import resources
from .models import Ubicacion
from .admin import UbicacionResource
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
