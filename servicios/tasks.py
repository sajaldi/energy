from celery import shared_task
import traceback


def try_decode(content, encodings=['utf-8-sig', 'iso-8859-1', 'windows-1252', 'utf-8']):
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode('utf-8', errors='ignore')


@shared_task(bind=True, name='servicios.tasks.import_kpis_task')
def import_kpis_task(self, file_path, file_format, user_id=None, verification_mode=False, dry_run=False):
    from tablib import Dataset
    from django.core.files.storage import default_storage
    from django.core.cache import cache
    from .resources import KPIResource
    from .models import KPI
    from activos.models import RegistroImportacion
    from django.contrib.auth.models import User

    user = User.objects.get(id=user_id) if user_id else None

    cache_key = f"import_kpis_progress_{user_id}" if user_id else "import_kpis_progress_system"

    def set_error(msg, detail=''):
        """Guarda el error en cache con el mensaje completo y lo retorna."""
        full_msg = f"{msg}\n\nDetalle técnico:\n{detail}" if detail else msg
        err = {
            'status': 'error',
            'status_code': 'error',
            'message': full_msg,
            'percent': 0,
        }
        cache.set(cache_key, err, 3600)
        return err

    # 1. Leer archivo
    try:
        with default_storage.open(file_path, 'rb') as f:
            file_content = f.read()
        if file_format == 'csv':
            dataset = Dataset().load(try_decode(file_content), format='csv')
        elif file_format in ['xls', 'xlsx']:
            dataset = Dataset().load(file_content, format=file_format)
        else:
            return set_error(f"Formato de archivo no soportado: '{file_format}'")
    except Exception as e:
        return set_error(
            f"No se pudo leer el archivo '{file_path}'.",
            traceback.format_exc()
        )

    total_rows = len(dataset)

    if total_rows == 0:
        return set_error("El archivo está vacío (0 filas de datos).")

    progress_info = {
        'current': 0,
        'total': total_rows,
        'status': 'Iniciando verificación...' if verification_mode else 'Iniciando importación...',
        'percent': 0,
        'new': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0,
        'found': 0,
        'not_found': 0,
        'verification_mode': verification_mode,
    }
    cache.set(cache_key, progress_info, 3600)
    self.update_state(state='PROGRESS', meta=progress_info)

    # 2. Modo verificación
    if verification_mode:
        try:
            results = []
            codes_seen = set()
            codes_duplicated = set()
            found_count = 0
            not_found_count = 0

            for i, row in enumerate(dataset.dict, start=1):
                nombre = str(row.get('nombre') or '').strip()
                servicio = str(row.get('servicio') or '').strip()
                identifier = f"{servicio}-{nombre}"

                if not nombre:
                    status = "SIN NOMBRE"
                    not_found_count += 1
                elif identifier in codes_seen:
                    codes_duplicated.add(identifier)
                    status = "REPETIDO EN ARCHIVO"
                else:
                    codes_seen.add(identifier)
                    exists = KPI.objects.filter(nombre=nombre, servicio__nombre=servicio).exists()
                    if exists:
                        found_count += 1
                        status = "EXISTE (Se actualizará)"
                    else:
                        not_found_count += 1
                        status = "NO EXISTE (Se creará)"

                results.append(f"Fila {i}: '{nombre}' [{servicio}] → {status}")

                if i % 10 == 0 or i == total_rows:
                    progress_info.update({
                        'current': i,
                        'status': f'Verificando {i}/{total_rows}...',
                        'percent': int((i / total_rows) * 100),
                        'found': found_count,
                        'not_found': not_found_count,
                        'duplicates': len(codes_duplicated),
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
                'verification_mode': True,
            }
        except Exception as e:
            return set_error(
                f"Error durante la verificación en fila {i if 'i' in dir() else '?'}.",
                traceback.format_exc()
            )

    # 3. Importación (dry_run o real)
    else:
        registro = None
        if not dry_run:
            registro = RegistroImportacion.objects.create(
                nombre=f"Importación de KPIs - {total_rows} filas",
                tipo='KPIs',
                usuario=user,
                estado='PROCESANDO',
                total_filas=total_rows
            )

        try:
            resource = KPIResource()
            result = resource.import_data(dataset, dry_run=dry_run, raise_errors=False)

            detailed_errors = []
            for error in result.base_errors:
                detailed_errors.append(f"Error general: {str(error.error)}")
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
                'file_path': file_path,
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
            return set_error(
                f"Error crítico durante la {'simulación' if dry_run else 'importación'}: {str(e)}",
                traceback.format_exc()
            )

    # 4. Limpiar archivo temporal (solo en importación real)
    if not dry_run:
        try:
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
        except Exception:
            pass

    cache.set(cache_key, final_res, 3600)
    return final_res
