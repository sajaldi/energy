from celery import shared_task
import traceback


def try_decode(content, encodings=['utf-8-sig', 'utf-8', 'windows-1252', 'iso-8859-1', 'utf-16', 'mac_roman']):
    for encoding in encodings:
        try:
            decoded = content.decode(encoding)
            if encoding in ['iso-8859-1', 'windows-1252', 'latin-1'] and '\x00' in decoded:
                continue
            return decoded
        except (UnicodeDecodeError, AttributeError):
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


# ================================================================
# RAG / Vectorización de KPIs
# ================================================================

def get_ollama_embedding(text):
    """Obtiene embedding desde Ollama local."""
    from django.conf import settings
    import requests
    
    url = f"{settings.OLLAMA_URL}/api/embeddings"
    payload = {
        "model": settings.OLLAMA_MODEL_EMBEDDING,
        "prompt": text
    }
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        embedding = response.json().get("embedding")
        # Si el modelo tiene más dimensiones de las esperadas (384), truncamos o avisamos.
        # Nomic-embed-text tiene 768, pero podemos truncar si es necesario para el VectorField(384)
        return embedding[:384] if embedding else None
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error en Ollama embedding: {str(e)}")
        return None

@shared_task(name='servicios.tasks.generate_kpi_embedding')
def generate_kpi_embedding(kpi_id):
    """
    Genera embeddings vectoriales para un KPI usando la infraestructura de IA disponible.
    Compone un texto rico con todos los campos del KPI, lo fragmenta,
    y almacena los fragmentos con sus embeddings para búsqueda semántica.
    """
    from .models import KPI, KPIFragmento
    from core.ai_utils import get_embedding
    import logging

    logger = logging.getLogger(__name__)

    try:
        kpi = KPI.objects.select_related('servicio').get(pk=kpi_id)
        
        # 1. Componer texto rico del KPI
        parts = [
            f"Servicio: {kpi.servicio.nombre}",
            f"KPI: {kpi.nombre}" if kpi.nombre else "",
            f"Categoría: {kpi.get_categoria_display()}",
            f"Estado: {kpi.get_estado_display()}",
        ]
        if kpi.descripcion:
            parts.append(f"Descripción: {kpi.descripcion}")
        if kpi.forma_de_cumplimiento:
            parts.append(f"Forma de cumplimiento: {kpi.forma_de_cumplimiento}")
        if kpi.metodo_de_supervision:
            parts.append(f"Método de supervisión: {kpi.metodo_de_supervision}")
        if kpi.comentarios:
            parts.append(f"Comentarios: {kpi.comentarios}")

        text = "\n".join(p for p in parts if p)

        if not text.strip():
            logger.warning(f"KPI {kpi_id} no tiene texto para generar embedding.")
            return False

        # 2. Limpiar fragmentos anteriores
        kpi.fragmentos.all().delete()

        # 3. Fragmentar (chunking)
        chunk_size = 1500
        overlap = 200
        chunks = []

        if len(text) <= chunk_size:
            chunks.append(text)
        else:
            start = 0
            while start < len(text):
                end = start + chunk_size
                if end < len(text):
                    last_space = text.rfind(' ', start, end)
                    if last_space != -1 and last_space > start:
                        end = last_space
                chunk_content = text[start:end].strip()
                if chunk_content:
                    chunks.append(chunk_content)
                start = end - overlap
                if start >= len(text):
                    break

        # 4. Generar Embeddings usando utilidad centralizada
        for i, chunk_content in enumerate(chunks):
            try:
                embedding_vector = get_embedding(chunk_content)
                if embedding_vector:
                    KPIFragmento.objects.create(
                        kpi=kpi,
                        contenido=chunk_content,
                        embedding=embedding_vector,
                        orden=i
                    )
            except Exception as e_api:
                logger.error(f"Error en generación de embedding para chunk {i} del KPI {kpi_id}: {str(e_api)}")
                continue

        # 5. Embedding resumen para el KPI
        try:
            res_embedding = get_embedding(text[:2000])
            if res_embedding:
                kpi.embedding = res_embedding
                kpi.save(update_fields=['embedding'])
        except Exception as e_res:
            logger.error(f"Error en embedding resumen del KPI {kpi_id}: {str(e_res)}")

        logger.info(f"Procesamiento de embeddings completado para KPI {kpi_id} ({len(chunks)} fragmentos).")
        return True

    except KPI.DoesNotExist:
        logger.error(f"KPI {kpi_id} no encontrado.")
        return False
    except Exception as e:
        logger.error(f"Error en generate_kpi_embedding: {str(e)}")
        return False


@shared_task(name='servicios.tasks.vectorize_all_kpis')
def vectorize_all_kpis():
    """
    Tarea masiva: re-indexa todos los KPIs activos para búsqueda semántica.
    Ideal para ejecutar tras una importación masiva o migración inicial.
    """
    from .models import KPI
    import logging

    logger = logging.getLogger(__name__)

    kpis = KPI.objects.all()
    total = kpis.count()

    for kpi in kpis:
        generate_kpi_embedding.delay(kpi.id)

    logger.info(f"Vectorización masiva iniciada: {total} KPIs encolados.")
    return {'status': 'enqueued', 'total': total}

