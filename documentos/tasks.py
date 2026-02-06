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
        
        with revision.archivo.open('rb') as f:
            content = f.read()
            extracted_data = extract_metadata_from_file(content, revision.archivo.name)

        revision.datos_extraidos = extracted_data
        revision.estado_extraccion = 'COMPLETADO'
        revision.save()
        
        logger.info(f"Extracción completada para Revisión {revision_id}")
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
