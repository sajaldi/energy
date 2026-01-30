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
def import_rutinas_task(self, file_path, file_format, user_id=None, verification_mode=False, dry_run=False):
    """
    Tarea Celery para importar o VERIFICAR RUTINAS con seguimiento de progreso real.
    """
    from tablib import Dataset
    from django.core.files.storage import default_storage
    from .admin import RutinaResource
    from django.core.cache import cache
    from .models import Rutina

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
    missing_dataset = Dataset()
    missing_dataset.headers = dataset.headers
    
    # Estado inicial
    progress_info = {
        'current': 0, 
        'total': total_rows, 
        'status': 'Iniciando verificacion...' if verification_mode else 'Iniciando importacion...', 
        'percent': 0,
        'new': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0,
        'found': 0,
        'not_found': 0,
        'verification_mode': verification_mode
    }
    cache.set(cache_key, progress_info, 3600)
    self.update_state(state='PROGRESS', meta=progress_info)
    
    if verification_mode:
        results = []
        codes_seen = set()
        codes_duplicated = set()
        found_count = 0
        not_found_count = 0
        
        for i, row in enumerate(dataset.dict, start=1):
            codigo = str(row.get('codigo_rutina') or '').strip()
            
            if not codigo:
                status = "SIN CODIGO"
                not_found_count += 1
                # Agregar a faltantes si tiene nombre o algo mas
                missing_dataset.append(dataset[i-1])
            else:
                if codigo in codes_seen:
                    codes_duplicated.add(codigo)
                    status = "REPETIDO EN ARCHIVO"
                else:
                    codes_seen.add(codigo)
                    exists = Rutina.objects.filter(codigo_rutina=codigo).exists()
                    if exists:
                        found_count += 1
                        status = "EXISTE"
                    else:
                        not_found_count += 1
                        status = "NO EXISTE"
                        missing_dataset.append(dataset[i-1])
            
            results.append(f"Fila {i}: Codigo '{codigo}' -> {status}")
            
            if i % 10 == 0 or i == total_rows:
                progress_info.update({
                    'current': i,
                    'status': f'Verificando {i}/{total_rows}...',
                    'percent': int((i / total_rows) * 100),
                    'found': found_count,
                    'not_found': not_found_count,
                    'duplicates': len(codes_duplicated)
                })
                cache.set(cache_key, progress_info, 3600)
                self.update_state(state='PROGRESS', meta=progress_info)

        final_res = {
            'status': 'completed',
            'status_code': 'completed',
            'total': total_rows,
            'found': found_count,
            'not_found': not_found_count,
            'duplicates': len(codes_duplicated),
            'duplicate_list': list(codes_duplicated),
            'results': results,
            'verification_mode': True
        }
    else:
        # Modo IMPORTACIÓN real
        resource.before_import(dataset)
        try:
            # Usar import_data que es mucho más robusto para detectar duplicados/actualizaciones
            # basado en import_id_fields configurado en el Resource.
            result = resource.import_data(dataset, dry_run=dry_run, raise_errors=False)
            
            # Recopilar errores detallados de las filas
            detailed_errors = []
            for error in result.base_errors:
                detailed_errors.append(f"Error General: {str(error.error)}")
            
            for line, errors in result.row_errors():
                for error in errors:
                    # Incluimos el numero de fila para que el usuario sepa donde esta el fallo
                    detailed_errors.append(f"Fila {line}: {str(error.error)}")

            final_res = {
                'status': 'completed',
                'status_code': 'completed',
                'total': total_rows,
                'new': result.totals.get('new', 0),
                'updated': result.totals.get('update', 0),
                'skipped': result.totals.get('skip', 0),
                'errors': len(detailed_errors),
                'error_list': detailed_errors,
                'verification_mode': False,
                'dry_run': dry_run,
                'file_path': file_path
            }
        except Exception as e:
            error_msg = f"Error crítico en importación: {str(e)}"
            progress_info.update({'status': 'error', 'message': error_msg})
            cache.set(cache_key, progress_info, 3600)
            return {'status': 'error', 'message': error_msg}

    # Si estamos en verificacion y hay códigos faltantes, generar el archivo Excel
    if verification_mode and len(missing_dataset) > 0:
        try:
            from django.core.files.base import ContentFile
            missing_filename = f"imports/faltantes_rutinas_{user_id or 'anon'}_{int(time.time())}.xlsx"
            default_storage.save(missing_filename, ContentFile(missing_dataset.xlsx))
            final_res['missing_file_url'] = default_storage.url(missing_filename)
            final_res['missing_count'] = len(missing_dataset)
        except Exception as e:
            print(f"Error al generar archivo de faltantes: {str(e)}")

    # Limpiar archivo original SOLO si no es dry_run
    if not dry_run:
        try:
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
        except:
            pass
        
    cache.set(cache_key, final_res, 3600)
    return final_res
@shared_task(bind=True)
def import_ordenes_task(self, file_path, file_format, user_id=None):
    """
    Tarea Celery para importar ÓRDENES DE TRABAJO con seguimiento de progreso real.
    """
    print(f"DEBUG: Starting task import_ordenes_task for user_id={user_id}")
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
        'status': 'Iniciando importacion...', 
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
        
    # Recopilar errores detallados
    detailed_errors = []
    try:
        for error in result.base_errors:
            detailed_errors.append(f"Error General: {str(error.error)}")
        for line, errors in result.row_errors():
            for error in errors:
                msg = f"Fila {line}: {str(error.error)}"
                detailed_errors.append(msg)
    except: pass

    final_res = {
        'status': 'completed',
        'total': total_rows,
        'new': result.totals.get('new', 0),
        'updated': result.totals.get('update', 0),
        'skipped': result.totals.get('skip', 0),
        'errors': len(result.base_errors) + len(result.row_errors()),
        'error_list': detailed_errors
    }
    cache.set(cache_key, final_res, 3600)
    return final_res
