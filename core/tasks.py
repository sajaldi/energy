import logging
import os
import pandas as pd
from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from .models import Consumo, Medidor
from .admin import ConsumoResource
from activos.models.importacion import RegistroImportacion
import tablib
from import_export.instance_loaders import ModelInstanceLoader

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def import_consumo_task(self, file_path, user_id=None):
    """
    Tarea asíncrona para importar datos de consumo desde Excel/CSV.
    """
    from django.core.files.storage import default_storage
    
    # 1. Inicialización de estado y registro
    self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100, 'message': 'Iniciando importación...'})
    
    registro = RegistroImportacion.objects.create(
        nombre=f"Importación de Consumos: {os.path.basename(file_path)}",
        tipo="Consumo Energía",
        usuario_id=user_id,
        estado='PROCESANDO'
    )

    results = {
        'total_rows': 0,
        'success_count': 0,
        'error_count': 0,
        'errors': [] # Lista de strings descriptivos
    }

    try:
        # 2. Cargar archivo
        if not default_storage.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        with default_storage.open(file_path, 'rb') as f:
            content = f.read()
            
        # Determinar formato
        if file_path.endswith('.xlsx'):
            dataset = tablib.Dataset().load(content, format='xlsx')
        elif file_path.endswith('.xls'):
            dataset = tablib.Dataset().load(content, format='xls')
        else:
            # CSV con detección de encoding
            success = False
            for enc in ['utf-8-sig', 'iso-8859-1', 'windows-1252', 'utf-8']:
                try:
                    dataset = tablib.Dataset().load(content.decode(enc), format='csv')
                    success = True
                    break
                except Exception:
                    continue
            if not success:
                raise ValueError("No se pudo decodificar el archivo CSV.")

        results['total_rows'] = len(dataset)
        total = len(dataset)
        
        if total == 0:
            return {'status': 'error', 'message': 'El archivo está vacío.'}

        # 3. Preparar Resource e Instance Loader
        resource = ConsumoResource()
        # Precargar medidores en el resource (como ya lo hace el resource.before_import)
        resource.before_import(dataset)
        
        # Instance loader para IE 4.x (ayuda a encontrar duplicados)
        instance_loader = ModelInstanceLoader(resource, dataset)

        # 4. Procesamiento fila por fila
        with transaction.atomic():
            for i, row in enumerate(dataset.dict, start=1):
                try:
                    # Importar fila usando la lógica del Resource
                    # row_number es requerido en versiones recientes
                    row_result = resource.import_row(row, instance_loader, row_number=i, dry_run=False)
                    
                    if row_result.import_type == 'error':
                        error_msg = f"Fila {i}: {str(row_result.errors[0].error)}"
                        results['errors'].append(error_msg)
                        results['error_count'] += 1
                    elif row_result.import_type == 'skip':
                        # Se saltó (probablemente duplicado o sin cambios)
                        results['success_count'] += 1
                    else:
                        results['success_count'] += 1

                except Exception as e:
                    results['errors'].append(f"Fila {i}: Error inesperado: {str(e)}")
                    results['error_count'] += 1

                # 5. Notificar progreso cada 10 filas o al final
                if i % 10 == 0 or i == total:
                    self.update_state(
                        state='PROGRESS', 
                        meta={
                            'current': i, 
                            'total': total, 
                            'success': results['success_count'],
                            'errors': results['error_count'],
                            'last_errors': results['errors'][-5:] # Enviar solo los últimos 5 para no saturar
                        }
                    )

        # 6. Finalizar Registro
        registro.estado = 'COMPLETADO'
        registro.total_filas = total
        registro.filas_nuevas = results['success_count']
        registro.filas_error = results['error_count']
        registro.detalles_error = "\n".join(results['errors'][:10])
        registro.save()

        # 7. Limpieza y Retorno
        # Eliminar archivo temporal si se desea
        # default_storage.delete(file_path)

        return {
            'status': 'done',
            'total': total,
            'success': results['success_count'],
            'errors_count': results['error_count'],
            'errors_list': results['errors'][:50] # Limitar reporte final
        }

    except Exception as e:
        logger.error(f"Error crítico en import_consumo_task: {e}", exc_info=True)
        if 'registro' in locals():
            registro.estado = 'ERROR'
            registro.detalles_error = str(e)
            registro.save()
        return {
            'status': 'error',
            'message': str(e)
        }
