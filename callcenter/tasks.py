import os
from celery import shared_task
from django.conf import settings
from .scraper import download_tickets_excel
from .utils import import_tickets_from_df
import pandas as pd
import logging

logger = logging.getLogger(__name__)

@shared_task(name='callcenter.tasks.sync_tickets_task')
def sync_tickets_task(days=2):
    """
    Tarea de Celery para sincronizar tickets desde SIG GIA.
    """
    # Estas credenciales deberían estar en variables de entorno o settings por seguridad
    username = os.environ.get('CALLCENTER_USER')
    password = os.environ.get('CALLCENTER_PASS')
    if not username or not password:
        logger.error("CALLCENTER_USER o CALLCENTER_PASS no están configurados en las variables de entorno.")
        return {"status": "error", "message": "Credenciales no configuradas (ver CALLCENTER_USER / CALLCENTER_PASS)"}
    company = "Centro Cívico Gubernamental de Honduras"
    
    logger.info(f"Iniciando sincronización de tickets de los últimos {days} días...")
    
    try:
        download_dir = os.path.join(settings.BASE_DIR, 'downloads')
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
            
        file_path = download_tickets_excel(
            username=username,
            password=password,
            company_name=company,
            days=days,
            download_dir=download_dir
        )
        
        if not file_path or not os.path.exists(file_path):
            error_msg = "No se pudo descargar el archivo de tickets."
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

        from django.db import connection, close_old_connections
        # Asegurar conexión limpia para el worker tras el scraping largo
        close_old_connections()
        if connection.connection:
            connection.close() 
            
        df = pd.read_excel(file_path)
        creados, actualizados = import_tickets_from_df(df)
        
        result_msg = f"Sincronización finalizada. Nuevos: {creados}, Actualizados: {actualizados}"
        logger.info(result_msg)
        
        # El archivo queda en downloads para trazabilidad si se desea
        # if os.path.exists(file_path):
        #     os.remove(file_path)
            
        return {"status": "success", "creados": creados, "actualizados": actualizados}
        
    except Exception as e:
        logger.error(f"Error en sync_tickets_task: {e}")
        return {"status": "error", "message": str(e)}

@shared_task(name='callcenter.tasks.sync_single_ticket_task')
def sync_single_ticket_task(ticket_id):
    """
    Tarea de Celery para sincronizar un único ticket de forma asíncrona.
    """
    from .models import SolicitudTicket
    from .scraper import sync_individual_ticket
    
    try:
        ticket = SolicitudTicket.objects.get(id=ticket_id)
        
        username = os.environ.get('CALLCENTER_USER')
        password = os.environ.get('CALLCENTER_PASS')
        company = "Centro Cívico Gubernamental de Honduras"

        if not username or not password:
            return {"status": "error", "message": "Credenciales no configuradas."}

        # Ejecutar el robot scraper
        result = sync_individual_ticket(
            username=username, 
            password=password, 
            company_name=company, 
            ticket_folio=ticket.folio, 
            fecha_solicitud=ticket.fecha_solicitud
        )
        
        return result

    except Exception as e:
        logger.error(f"Error en sync_single_ticket_task para ticket {ticket_id}: {e}")
        return {"status": "error", "message": str(e)}

@shared_task(name='callcenter.tasks.vectorize_ticket_n8n')
def vectorize_ticket_n8n(ticket_id):
    """
    Envía los datos del ticket al webhook de n8n para generación de embedding.
    """
    from .models import SolicitudTicket
    import requests
    import json
    
    try:
        ticket = SolicitudTicket.objects.select_related('ubicacion').get(id=ticket_id)
        
        n8n_url = getattr(settings, 'N8N_TICKET_VECTORIZER_URL', None)
        if not n8n_url:
            logger.warning("N8N_TICKET_VECTORIZER_URL no está configurada.")
            return False
            
        # Construir el contexto total (todas las etiquetas relevantes)
        context_parts = []
        if ticket.folio: context_parts.append(f"FOLIO: {ticket.folio}")
        if ticket.solicitante: context_parts.append(f"SOLICITANTE: {ticket.solicitante}")
        if ticket.servicio: context_parts.append(f"SERVICIO: {ticket.servicio} > {ticket.subservicio or ''}")
        if ticket.ubicacion: context_parts.append(f"UBICACION: {ticket.ubicacion.ruta_completa}")
        elif ticket.nivel: context_parts.append(f"UBICACION: {ticket.nivel} > {ticket.grupo or ''}")
        
        if ticket.solicitud_descripcion: context_parts.append(f"SOLICITUD: {ticket.solicitud_descripcion}")
        if ticket.falla_descripcion: context_parts.append(f"FALLA: {ticket.falla_descripcion} ({ticket.falla_clasificacion or ''})")
        if ticket.diagnostico: context_parts.append(f"DIAGNOSTICO: {ticket.diagnostico}")
        if ticket.actividades: context_parts.append(f"ACTIVIDADES: {ticket.actividades}")
        if ticket.observaciones: context_parts.append(f"OBSERVACIONES: {ticket.observaciones}")
        if ticket.observaciones_usuario: context_parts.append(f"OBS. USUARIO: {ticket.observaciones_usuario}")
        if ticket.clasificacion_falla_final: context_parts.append(f"FALLA FINAL: {ticket.clasificacion_falla_final}")
        if ticket.categoria_falla: context_parts.append(f"CATEGORIA: {ticket.categoria_falla}")

        rich_context = " | ".join(context_parts)
        # Añadir instrucción para mxbai-embed-large para mejorar recuperación
        rich_context = f"Represent this document for retrieval: {rich_context}"

        payload = {
            'ticket_id': ticket.id,
            'folio': ticket.folio,
            'rich_context': rich_context,
            'fecha_solicitud': ticket.fecha_solicitud.isoformat() if ticket.fecha_solicitud else None,
            # Mantener campos individuales por si n8n los usa para lógica condicional
            'servicio': ticket.servicio or '',
            'ubicacion': ticket.ubicacion.nombre if ticket.ubicacion else '',
            'categoria_falla': ticket.categoria_falla or '',
            'callback_url': f"{settings.INTERNAL_SITE_URL}/callcenter/api/webhook/vector-update/"
        }
        
        logger.info(f"Enviando ticket {ticket.folio} a n8n para vectorización: {n8n_url}")
        response = requests.post(n8n_url, json=payload, timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info(f"Ticket {ticket.folio} enviado exitosamente.")
            return True
        else:
            logger.error(f"Error enviando ticket {ticket.folio} a n8n. Status: {response.status_code}")
            return False
            
    except ObjectDoesNotExist:
        logger.warning(f"Ticket {ticket_id} no encontrado para vectorización.")
        return False
    except Exception as e:
        logger.error(f"Error en vectorize_ticket_n8n para ticket {ticket_id}: {e}")
        return False

@shared_task(name='callcenter.tasks.bulk_vectorize_n8n')
def bulk_vectorize_n8n(only_missing=True):
    """
    Envía tickets en lote a n8n para análisis.
    """
    from .models import SolicitudTicket
    
    if only_missing:
        tickets = SolicitudTicket.objects.filter(embedding__isnull=True)
    else:
        tickets = SolicitudTicket.objects.all()
        
    count = 0
    total = tickets.count()
    logger.info(f"Iniciando envío masivo a n8n: {total} tickets.")
    
    for ticket in tickets:
        vectorize_ticket_n8n.delay(ticket.id)
        count += 1
        
    return {"status": "success", "sent": count, "total": total}

@shared_task(name='callcenter.tasks.bulk_vectorize_tickets')
def bulk_vectorize_tickets():
    """
    Procesa TODOS los tickets sin embedding usando Ollama local.
    Genera el embedding directamente y lo guarda en la BD.
    """
    from .models import SolicitudTicket
    import requests
    
    ollama_url = f'{settings.OLLAMA_API_URL}/api/embeddings'
    
    tickets = SolicitudTicket.objects.select_related('ubicacion').filter(
        embedding__isnull=True
    )
    total = tickets.count()
    logger.info(f"[VECTORIZE] Iniciando vectorización masiva: {total} tickets pendientes")
    
    procesados = 0
    errores = 0
    
    for ticket in tickets.iterator():
        try:
            # Construir prompt rico en contexto
            partes = [f"TICKET: {ticket.folio or ''}"]
            
            if ticket.ubicacion:
                partes.append(f"UBICACIÓN: {ticket.ubicacion.nombre}")
            elif ticket.nivel:
                partes.append(f"UBICACIÓN: {ticket.nivel} - {ticket.grupo or ''}")
            
            if ticket.servicio:
                partes.append(f"SERVICIO: {ticket.servicio} - {ticket.subservicio or ''}")
            
            if ticket.solicitud_descripcion:
                partes.append(f"DESCRIPCIÓN: {ticket.solicitud_descripcion}")
            
            if ticket.falla_descripcion:
                partes.append(f"FALLA: {ticket.falla_descripcion}")
            
            if ticket.diagnostico:
                partes.append(f"DIAGNÓSTICO: {ticket.diagnostico}")
                
            prompt_text = " | ".join(partes)
            
            # Llamar a Ollama
            resp = http_requests.post(ollama_url, json={
                'model': 'mxbai-embed-large',
                'prompt': f"Represent this document for retrieval: {prompt_text}"
            }, timeout=15)
            
            if resp.status_code == 200:
                embedding = resp.json().get('embedding')
                if embedding:
                    ticket.embedding = embedding
                    ticket.save(update_fields=['embedding'])
                    procesados += 1
                else:
                    errores += 1
            else:
                errores += 1
                logger.warning(f"Ollama error {resp.status_code} para ticket {ticket.folio}")
            
            if procesados % 50 == 0 and procesados > 0:
                logger.info(f"[VECTORIZE] Progreso: {procesados}/{total} procesados, {errores} errores")
                
        except Exception as e:
            errores += 1
            logger.error(f"Error vectorizando ticket {ticket.id}: {e}")
            continue
    
    msg = f"[VECTORIZE] Finalizado: {procesados}/{total} procesados, {errores} errores"
    logger.info(msg)
    return {"procesados": procesados, "total": total, "errores": errores}
