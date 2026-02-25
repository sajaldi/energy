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

@shared_task(bind=True, name='mantenimiento.tasks.import_rutinas_task')
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
    print(f"[DEBUG] [Task] Iniciando import_rutinas_task. verif={verification_mode}, dry={dry_run}, user={user_id}")
    import sys
    sys.stdout.flush()

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
            print(f"[DEBUG] [Task] Verificando fila {i}: {codigo} -> {status}")
            
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
@shared_task(bind=True, name='mantenimiento.tasks.import_ordenes_task')
def import_ordenes_task(self, file_path, file_format, user_id=None, verification_mode=False, dry_run=False):
    """
    Tarea Celery para importar o VERIFICAR OTs con seguimiento de progreso real.
    """
    from tablib import Dataset
    from django.core.files.storage import default_storage
    from .admin import OrdenTrabajoResource
    from django.core.cache import cache
    from .models import OrdenTrabajo
    import sys

    # Inicializar resource
    resource = OrdenTrabajoResource()
    resource._meta.use_bulk = False
    
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
    print(f"[DEBUG] [Task] Iniciando import_ordenes_task. verif={verification_mode}, dry={dry_run}, user={user_id}")
    sys.stdout.flush()

    if verification_mode:
        results = []
        codes_seen = set()
        codes_duplicated = set()
        found_count = 0
        not_found_count = 0
        
        for i, row in enumerate(dataset.dict, start=1):
            codigo = str(row.get('codigo_de_orden') or '').strip()
            
            if not codigo or codigo.lower() in ['none', 'nan', 'null', '']:
                status = "SIN CODIGO"
                not_found_count += 1
                missing_dataset.append(dataset[i-1])
            else:
                if codigo in codes_seen:
                    codes_duplicated.add(codigo)
                    status = "REPETIDO EN ARCHIVO"
                else:
                    codes_seen.add(codigo)
                    exists = OrdenTrabajo.objects.filter(codigo_de_orden=codigo).exists()
                    if exists:
                        found_count += 1
                        status = "EXISTE (Se actualizará)"
                    else:
                        not_found_count += 1
                        status = "NO EXISTE (Se creará)"
            
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
        # Modo IMPORTACIÓN real o Dry Run
        resource.before_import(dataset)
        try:
            print(f"[DEBUG] [Task] Ejecutando resource.import_data. dry_run={dry_run}")
            # Usar import_data para consistencia y robustez
            result = resource.import_data(dataset, dry_run=dry_run, raise_errors=False)
            print(f"[DEBUG] [Task] import_data finalizado. Totals: {result.totals}")
            
            # Recopilar errores
            detailed_errors = []
            for error in result.base_errors:
                detailed_errors.append(f"Error General: {str(error.error)}")
            
            for line, errors in result.row_errors():
                for error in errors:
                    detailed_errors.append(f"Fila {line}: {str(error.error)}")
                    
            if result.invalid_rows:
                for row in result.invalid_rows:
                    error_msg = f"Fila {row.number} (Invalid): {str(row.error)}"
                    detailed_errors.append(error_msg)
                    # Force print to stdout for capturing in logs
                    print(f"[DEBUG] [Task] INVALID ROW DETECTED: {error_msg}")
                    print(f"[DEBUG] [Task] Row Values: {row.values}")
            
            if detailed_errors:
                print(f"[DEBUG] [Task] Errores encontrados: {detailed_errors}")

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

    # Limpiar archivo original SOLO si no es dry_run
    if not dry_run:
        try:
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
        except:
            pass
        
    cache.set(cache_key, final_res, 3600)
    return final_res


@shared_task(bind=True, name='mantenimiento.tasks.import_avisos_task')
def import_avisos_task(self, file_path, file_format, user_id=None, verification_mode=False, dry_run=False):
    from tablib import Dataset
    from django.core.files.storage import default_storage
    from .admin import AvisoResource
    from django.core.cache import cache
    from .models import Aviso
    from activos.models import RegistroImportacion
    from django.contrib.auth.models import User
    import sys

    user = User.objects.get(id=user_id) if user_id else None

    resource = AvisoResource()
    cache_key = f"import_avisos_progress_{user_id}" if user_id else "import_avisos_progress_system"

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
    sys.stdout.flush()

    if verification_mode:
        results = []
        codes_seen = set()
        codes_duplicated = set()
        found_count = 0
        not_found_count = 0
        
        # En Avisos, identificamos por id o descripción+fecha (aquí no suele haber update masivo, 
        # pero asumimos import id = id o un nuevo aviso)
        for i, row in enumerate(dataset.dict, start=1):
            aviso_id = str(row.get('id') or '').strip()
            
            identifier = aviso_id
            
            if not aviso_id:
                status = "NUEVO REGISTRO (Se creará)"
                not_found_count += 1
            else:
                if identifier in codes_seen:
                    codes_duplicated.add(identifier)
                    status = "REPETIDO EN ARCHIVO"
                else:
                    codes_seen.add(identifier)
                    exists = Aviso.objects.filter(id=aviso_id).exists()
                    if exists:
                        found_count += 1
                        status = "EXISTE (Se actualizará)"
                    else:
                        not_found_count += 1
                        status = "ID NO EXISTE (Error posible)"
            
            results.append(f"Fila {i}: ID '{aviso_id}' -> {status}")
            
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
        registro = None
        if not dry_run:
            registro = RegistroImportacion.objects.create(
                nombre=f"Importación de Avisos - {total_rows} filas",
                tipo='Avisos',
                usuario=user,
                estado='PROCESANDO',
                total_filas=total_rows
            )
        resource.before_import(dataset)
        try:
            result = resource.import_data(dataset, dry_run=dry_run, raise_errors=False)
            
            detailed_errors = []
            for error in result.base_errors:
                detailed_errors.append(f"Error General: {str(error.error)}")
            
            for line, errors in result.row_errors():
                for error in errors:
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

            if registro:
                registro.filas_nuevas = final_res.get('new', 0)
                registro.filas_actualizadas = final_res.get('updated', 0)
                registro.filas_omitidas = final_res.get('skipped', 0)
                registro.filas_error = final_res.get('errors', 0)
                registro.estado = 'COMPLETADO'
                if final_res.get('error_list'):
                    registro.detalles_error = "\n".join(final_res['error_list'][:10])
                registro.save()
        except Exception as e:
            error_msg = f"Error crítico en importación: {str(e)}"
            progress_info.update({'status': 'error', 'message': error_msg})
            cache.set(cache_key, progress_info, 3600)
            return {'status': 'error', 'message': error_msg}

    if not dry_run:
        try:
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
        except:
            pass
        
    cache.set(cache_key, final_res, 3600)
    return final_res
@shared_task(bind=True, name='mantenimiento.tasks.import_personal_task')
def import_personal_task(self, file_path, file_format, user_id=None, verification_mode=False, dry_run=False):
    """
    Tarea Celery para importar o VERIFICAR PERSONAL (Técnicos) con seguimiento de progreso real.
    """
    from tablib import Dataset
    from django.core.files.storage import default_storage
    from .admin import TecnicoPuestoResource
    from django.core.cache import cache
    from .models import TecnicoPuesto
    from django.contrib.auth.models import User
    import sys

    # Inicializar resource
    resource = TecnicoPuestoResource()
    
    # Marcador de progreso en caché
    cache_key = f"import_personal_progress_{user_id}" if user_id else "import_personal_progress_system"

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
    print(f"[DEBUG] [Task] Iniciando import_personal_task. verif={verification_mode}, dry={dry_run}, user={user_id}")
    sys.stdout.flush()

    if verification_mode:
        results = []
        codes_seen = set()
        codes_duplicated = set()
        found_count = 0
        not_found_count = 0
        
        for i, row in enumerate(dataset.dict, start=1):
            dni = str(row.get('dni') or '').strip()
            username = str(row.get('username') or '').strip()
            
            identifier = dni if dni else username
            
            if not identifier:
                status = "SIN DNI NI USERNAME"
                not_found_count += 1
                missing_dataset.append(dataset[i-1])
            else:
                if identifier in codes_seen:
                    codes_duplicated.add(identifier)
                    status = "REPETIDO EN ARCHIVO"
                else:
                    codes_seen.add(identifier)
                    
                    exists = False
                    if dni:
                        exists = TecnicoPuesto.objects.filter(dni=dni).exists()
                    elif username:
                        exists = TecnicoPuesto.objects.filter(user__username=username).exists()
                        
                    if exists:
                        found_count += 1
                        status = "EXISTE (Se actualizará)"
                    else:
                        not_found_count += 1
                        status = "NO EXISTE (Se creará)"
            
            results.append(f"Fila {i}: '{identifier}' -> {status}")
            
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
        # Modo IMPORTACIÓN real o Dry Run
        resource.before_import(dataset) # Normaliza headers si fuera necesario
        try:
            print(f"[DEBUG] [Task] Ejecutando resource.import_data. dry_run={dry_run}")
            result = resource.import_data(dataset, dry_run=dry_run, raise_errors=False)
            
            # Recopilar errores
            detailed_errors = []
            for error in result.base_errors:
                detailed_errors.append(f"Error General: {str(error.error)}")
            
            for line, errors in result.row_errors():
                for error in errors:
                    detailed_errors.append(f"Fila {line}: {str(error.error)}")
            
            if result.invalid_rows:
                for row in result.invalid_rows:
                    detailed_errors.append(f"Fila {row.number} (Invalid): {str(row.error)}")

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

    # Limpiar archivo original SOLO si no es dry_run
    if not dry_run:
        try:
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
        except:
            pass
        
    cache.set(cache_key, final_res, 3600)
    return final_res
@shared_task(bind=True, name='mantenimiento.tasks.import_procedimientos_task')
def import_procedimientos_task(self, file_path, file_format, user_id=None, verification_mode=False, dry_run=False):
    """
    Tarea Celery para importar PROCEDIMIENTOS y PASOS.
    """
    from tablib import Dataset
    from django.core.files.storage import default_storage
    from .admin import PasoProcedimientoResource
    from django.core.cache import cache
    from .models import Procedimiento
    import sys

    resource = PasoProcedimientoResource()
    cache_key = f"import_procedimientos_progress_{user_id}" if user_id else "import_procedimientos_progress_system"

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
    progress_info = {
        'current': 0, 
        'total': total_rows, 
        'status': 'Procesando archivo...', 
        'percent': 0,
        'new': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0,
        'verification_mode': verification_mode
    }
    cache.set(cache_key, progress_info, 3600)
    self.update_state(state='PROGRESS', meta=progress_info)

    try:
        # Usamos PasoProcedimientoResource porque permite crear Procedimiento y Pasos
        result = resource.import_data(dataset, dry_run=dry_run, raise_errors=False)
        
        detailed_errors = []
        for error in result.base_errors:
            detailed_errors.append(f"Error General: {str(error.error)}")
        for line, errors in result.row_errors():
            for error in errors:
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
        error_msg = f"Error crítico: {str(e)}"
        cache.set(cache_key, {'status': 'error', 'message': error_msg}, 3600)
        return {'status': 'error', 'message': error_msg}

    if not dry_run:
        try:
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
        except: pass
        
    cache.set(cache_key, final_res, 3600)
    return final_res
