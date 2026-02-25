import logging
from celery import shared_task
from django.core.files.storage import default_storage
import os
import tempfile
import json

logger = logging.getLogger(__name__)

@shared_task(name='documentos.tasks.extract_document_metadata')
def extract_document_metadata(revision_id):
    """
    Tarea para extraer texto y metadatos de un documento (PDF, etc.)
    """
    from .models import Revision
    try:
        revision = Revision.objects.get(pk=revision_id)
        revision.estado_extraccion = 'PROCESANDO'
        revision.save()

        if not revision.archivo:
            revision.estado_extraccion = 'ERROR'
            revision.datos_extraidos = {'error': 'No hay archivo asociado'}
            revision.save()
            return

        from .utils_extraer import extract_metadata_from_file
        import requests
        from django.conf import settings
        
        # 1. Extracción Local (PyMuPDF)
        with revision.archivo.open('rb') as f:
            content = f.read()
            local_data = extract_metadata_from_file(content, revision.archivo.name)

        # 2. Consultar n8n para Conversión a PDF y Metadatos IA
        n8n_url = getattr(settings, 'N8N_PROCESS_DOCUMENT_WEBHOOK_URL', None)
        if n8n_url:
            try:
                # Usar la URL firmada de S3/MinIO para que n8n no necesite credenciales adicionales
                internal_file_url = revision.archivo.url
                # Forzamos a que el callback use el Túnel Reverso (localhost:8080) que n8n sí puede ver
                base_callback_url = getattr(settings, 'INTERNAL_SITE_URL', 'http://localhost:8080')
                internal_callback_url = f"{base_callback_url}/documentos/api/callback-procesamiento/{revision.id}/"

                payload = {
                    'revision_id': revision.id,
                    'documento_id': revision.documento.id,
                    'filename': os.path.basename(revision.archivo.name),
                    'file_url': internal_file_url,
                    'file_key': revision.archivo.name,
                    'file_path': revision.archivo.name,
                    'tipo_documento': revision.documento.tipo_documento.nombre,
                    'todos_los_tipos': list(revision.documento.tipo_documento.__class__.objects.values_list('nombre', flat=True)),
                    'callback_url': internal_callback_url,
                    'metadatos_requeridos': list(revision.documento.tipo_documento.metadatos_config.values_list('nombre', flat=True))
                }
                print(f"-------- DEBUG N8N CALL --------")
                print(f"URL: {n8n_url}")
                print(f"Payload: {json.dumps(payload, indent=2)}")
                
                # Llamada asíncrona hacia n8n - n8n responderá al callback para finalizar
                resp = requests.post(n8n_url, json=payload, timeout=10)
                print(f"Response Status: {resp.status_code}")
                logger.info(f"Revision {revision_id}: Enviada a n8n. Status: {resp.status_code}")
            except Exception as e_n8n:
                print(f"Error llamando a n8n: {str(e_n8n)}")
                logger.error(f"Error llamando a n8n: {e_n8n}")
        
        # Guardar resultados locales
        revision.datos_extraidos = local_data
        
        # Si no hubo n8n, marcamos como completado. Si hubo, esperamos el callback (PROCESANDO)
        if not n8n_url:
            revision.estado_extraccion = 'COMPLETADO'
            
        revision.save()
        
        logger.info(f"Extracción local completada para Revisión {revision_id}. Esperando n8n: {bool(n8n_url)}")
        return True

    except Exception as e:
        logger.error(f"Error fatal en extract_document_metadata: {str(e)}")
        try:
            revision = Revision.objects.get(pk=revision_id)
            revision.estado_extraccion = 'ERROR'
            revision.datos_extraidos = {'error': str(e)}
            revision.save()
        except:
            pass
        return False

@shared_task(bind=True)
def import_comentarios_task(self, file_path, file_format, user_id=None, verification_mode=False, dry_run=False):
    """
    Tarea Celery para importar Comentarios de Documentos con seguimiento de progreso real.
    """
    from tablib import Dataset
    from django.core.files.storage import default_storage
    from .resources import ComentarioDocumentoResource
    from django.core.cache import cache
    
    # Inicializar resource
    resource = ComentarioDocumentoResource()
    
    # Marcador de progreso en caché
    cache_key = f"import_comentarios_progress_{user_id}" if user_id else "import_comentarios_progress_system"

    # Leer archivo
    try:
        with default_storage.open(file_path, 'rb') as f:
            file_content = f.read()
            if file_format == 'csv':
                # Intentar decodificar con varios encodings
                decoded = None
                for enc in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
                    try:
                        decoded = file_content.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue
                if not decoded: decoded = file_content.decode('utf-8', errors='ignore')
                
                dataset = Dataset().load(decoded, format='csv')
            elif file_format in ['xls', 'xlsx']:
                dataset = Dataset().load(file_content, format=file_format)
            else:
                raise ValueError(f"Formato no soportado: {file_format}")
    except Exception as e:
        error_res = {'status': 'error', 'message': f'Error al leer archivo: {str(e)}'}
        cache.set(cache_key, error_res, 3600)
        return error_res

    total_rows = len(dataset)
    
    # Estado inicial
    progress_info = {
        'current': 0, 
        'total': total_rows, 
        'status': 'Iniciando importación...', 
        'percent': 0,
        'new': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0,
        'verification_mode': verification_mode
    }
    cache.set(cache_key, progress_info, 3600)
    self.update_state(state='PROGRESS', meta=progress_info)

    if verification_mode:
        # Modo Verificación (básico)
        results = []
        for i, row in enumerate(dataset.dict, start=1):
            doc_code = row.get('documento_codigo')
            status = "OK" if doc_code else "FALTA CODIGO DOCUMENTO"
            results.append(f"Fila {i}: {doc_code} -> {status}")
            
            if i % 10 == 0 or i == total_rows:
                progress_info.update({
                    'current': i,
                    'percent': int((i / total_rows) * 100)
                })
                cache.set(cache_key, progress_info, 3600)
                self.update_state(state='PROGRESS', meta=progress_info)

        final_res = {
            'status': 'completed',
            'total': total_rows,
            'results': results,
            'verification_mode': True
        }
    else:
        # Modo Importación Real
        try:
            resource.before_import(dataset)
            result = resource.import_data(dataset, dry_run=dry_run, raise_errors=False)

            detailed_errors = []
            for error in result.base_errors:
                detailed_errors.append(f"Error General: {str(error.error)}")
            for line, errors in result.row_errors():
                for error in errors:
                    detailed_errors.append(f"Fila {line}: {str(error.error)}")
            
            final_res = {
                'status': 'completed',
                'total': total_rows,
                'new': result.totals.get('new', 0),
                'updated': result.totals.get('update', 0),
                'skipped': result.totals.get('skip', 0),
                'errors': len(detailed_errors),
                'error_list': detailed_errors,
                'dry_run': dry_run,
                'file_path': file_path
            }
        except Exception as e:
             error_msg = f"Error crítico: {str(e)}"
             cache.set(cache_key, {'status': 'error', 'message': error_msg}, 3600)
             return {'status': 'error', 'message': error_msg}

    # Limpiar archivo si no es dry run
    if not dry_run and not verification_mode:
        try:
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
        except:
            pass

    cache.set(cache_key, final_res, 3600)
    return final_res

