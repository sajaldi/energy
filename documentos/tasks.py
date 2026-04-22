import logging
from celery import shared_task
from django.core.files.storage import default_storage
import os
import tempfile
import json

logger = logging.getLogger(__name__)
# Configuración global de encodings para importación
IMPORT_ENCODINGS = ['utf-8-sig', 'utf-8', 'windows-1252', 'iso-8859-1', 'utf-16', 'mac_roman']

def try_decode(content, encodings=None):
    """Intenta decodificar el contenido usando una lista de encodings prioritarios."""
    if encodings is None:
        encodings = IMPORT_ENCODINGS
    for encoding in encodings:
        try:
            decoded = content.decode(encoding)
            if encoding in ['iso-8859-1', 'windows-1252', 'latin-1'] and '\x00' in decoded:
                continue
            return decoded
        except (UnicodeDecodeError, AttributeError):
            continue
    return content.decode('utf-8', errors='replace')


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
                # Intentar decodificar con lógica robusta
                decoded = try_decode(file_content)

                
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

@shared_task(name='documentos.tasks.generate_document_embedding')
def generate_document_embedding(documento_id):
    """
    Genera embeddings vectoriales para el contenido de texto de un documento usando Google Gemini API.
    Fracciona el texto en fragmentos (chunking) para mejorar la calidad de la búsqueda en documentos largos.
    """
    from .models import Documento, DocumentoFragmento
    from django.conf import settings
    import google.generativeai as genai
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        if not settings.GEMINI_API_KEY:
            logger.warning(f"No hay GEMINI_API_KEY configurada. Abortando embedding para doc {documento_id}")
            return False
            
        genai.configure(api_key=settings.GEMINI_API_KEY)
        doc = Documento.objects.get(pk=documento_id)
        
        if not doc.contenido_texto:
            logger.warning(f"Documento {documento_id} no tiene texto para generar embedding.")
            return False
            
        # 1. Limpiar fragmentos anteriores para evitar duplicidad al re-procesar
        doc.fragmentos.all().delete()
            
        # 2. Lógica de Chunking (Fragmentación)
        text = doc.contenido_texto
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

        # 3. Generar Embeddings vía API Gemini
        # Usamos text-embedding-004 con dimensionalidad forzada a 384 para compatibilidad
        for i, chunk_content in enumerate(chunks):
            try:
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=chunk_content,
                    task_type="retrieval_document",
                    output_dimensionality=384
                )
                embedding_vector = result['embedding']
                
                DocumentoFragmento.objects.create(
                    documento=doc,
                    contenido=chunk_content,
                    embedding=embedding_vector,
                    orden=i
                )
            except Exception as e_api:
                logger.error(f"Error en Gemini API para chunk {i} del doc {documento_id}: {str(e_api)}")
                continue

        # 4. Generar embedding resumen para el documento (primeros 2000 chars)
        try:
            res_result = genai.embed_content(
                model="models/text-embedding-004",
                content=text[:2000],
                task_type="retrieval_document",
                output_dimensionality=384
            )
            doc.embedding = res_result['embedding']
            doc.save()
        except Exception as e_res:
             logger.error(f"Error en Gemini API para resumen del doc {documento_id}: {str(e_res)}")

        logger.info(f"Embedding Gemini generado para doc {documento_id} ({len(chunks)} chunks).")
        return True
        
    except Documento.DoesNotExist:
        logger.error(f"Documento {documento_id} no encontrado.")
        return False
    except Exception as e:
        logger.error(f"Error en generate_document_embedding: {str(e)}")
        return False

@shared_task(name='documentos.tasks.sync_document_embeddings')
def sync_document_embeddings():
    """
    Tarea periódica que busca documentos con texto pero sin fragmentos vectorizados
    y dispara su procesamiento usando Gemini.
    """
    from .models import Documento
    from django.db.models import Count
    
    # Buscar documentos que tienen contenido_texto pero no tienen fragmentos asociados
    docs_pendientes = Documento.objects.exclude(
        contenido_texto__isnull=True
    ).exclude(
        contenido_texto=''
    ).annotate(
        num_fragmentos=Count('fragmentos')
    ).filter(
        num_fragmentos=0
    )[:10]  # Procesar en lotes pequeños
    
    for doc in docs_pendientes:
        generate_document_embedding.delay(doc.id)
            
    return f"Sincronizados {docs_pendientes.count()} documentos pendientes."

