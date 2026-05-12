import os
from celery import shared_task
from django.conf import settings
from .scraper import download_tickets_excel
from .utils import import_tickets_from_df
import pandas as pd
import logging

logger = logging.getLogger(__name__)

@shared_task(name='callcenter.tasks.sync_tickets_task')
def sync_tickets_task(days=2, fecha_inicio=None, fecha_fin=None):
    """
    Tarea de Celery para sincronizar tickets desde SIG GIA.
    Si fecha_inicio y fecha_fin están definidos (formato dd/mm/yyyy), se usan esas fechas.
    De lo contrario, se usa el parámetro days para calcular el rango.
    """
    # Estas credenciales deberían estar en variables de entorno o settings por seguridad
    username = os.environ.get('CALLCENTER_USER')
    password = os.environ.get('CALLCENTER_PASS')
    if not username or not password:
        logger.error("CALLCENTER_USER o CALLCENTER_PASS no están configurados en las variables de entorno.")
        return {"status": "error", "message": "Credenciales no configuradas (ver CALLCENTER_USER / CALLCENTER_PASS)"}
    company = "Centro Cívico Gubernamental de Honduras"
    
    if fecha_inicio and fecha_fin:
        logger.info(f"Iniciando sincronización de tickets del {fecha_inicio} al {fecha_fin}...")
    else:
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
            download_dir=download_dir,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
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
        
        # Ubicación detallada
        if ticket.ubicacion: 
            context_parts.append(f"UBICACION: {ticket.ubicacion.ruta_completa}")
            if ticket.ubicacion.tipo: context_parts.append(f"TIPO UBICACION: {ticket.ubicacion.tipo}")
        else:
            loc_parts = [p for p in [ticket.area, ticket.nivel, ticket.grupo, ticket.unidad] if p]
            if loc_parts:
                context_parts.append(f"UBICACION: {' > '.join(loc_parts)}")
        
        # Activo si existe
        if ticket.activo:
            context_parts.append(f"ACTIVO: {ticket.activo.nombre} (Tag: {ticket.activo.tag or ''})")

        if ticket.solicitud_descripcion: context_parts.append(f"SOLICITUD: {ticket.solicitud_descripcion}")
        if ticket.falla_descripcion: context_parts.append(f"FALLA: {ticket.falla_descripcion} ({ticket.falla_clasificacion or ''})")
        if ticket.diagnostico: context_parts.append(f"DIAGNOSTICO: {ticket.diagnostico}")
        if ticket.actividades: context_parts.append(f"ACTIVIDADES: {ticket.actividades}")
        if ticket.observaciones: context_parts.append(f"OBSERVACIONES: {ticket.observaciones}")
        if ticket.observaciones_usuario: context_parts.append(f"OBS. USUARIO: {ticket.observaciones_usuario}")
        if ticket.clasificacion_falla_final: context_parts.append(f"FALLA FINAL: {ticket.clasificacion_falla_final}")
        if ticket.categoria_falla: context_parts.append(f"CATEGORIA: {ticket.categoria_falla}")

        # --- CONTEXTO VISUAL (NUEVO) ---
        # Incluir descripciones de IA de todas las evidencias analizadas
        visual_parts = []
        for ev in ticket.evidencias.filter(analizada=True):
            if ev.descripcion_ia:
                visual_parts.append(ev.descripcion_ia)
        
        if visual_parts:
            context_parts.append(f"ANALISIS VISUAL (IA): {' | '.join(visual_parts)}")

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
            }, timeout=60)
            
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

@shared_task(name='callcenter.tasks.analyze_image_ai')
def analyze_image_ai(evidencia_id):
    """
    Usa Ollama con un modelo multimodal (llava) para describir una imagen de evidencia.
    La descripción se guarda en descripcion_ia y luego se dispara la re-vectorización del ticket.
    """
    import base64
    import requests as http_requests
    from .models import EvidenciaTicket
    
    try:
        evidencia = EvidenciaTicket.objects.get(id=evidencia_id)
        if not evidencia.archivo:
            return False
            
        # 1. Preparar la imagen en Base64
        # Si estamos usando S3/MinIO, necesitamos descargarla o leerla desde el storage
        from django.core.files.storage import default_storage
        with default_storage.open(evidencia.archivo.name, 'rb') as f:
            encoded_string = base64.b64encode(f.read()).decode('utf-8')
            
        # 2. Llamar a Ollama (Modelo Moondream - Más ligero y rápido)
        ollama_url = f"{settings.OLLAMA_API_URL}/api/generate"
        prompt = (
            "Describe esta imagen de mantenimiento técnico de forma concisa pero detallada. "
            "Enfócate en fallas, daños, reparaciones o estado de equipos. "
            "Responde en español. No saludes, ve directo al grano."
        )
        
        payload = {
            "model": "moondream",
            "prompt": prompt,
            "stream": False,
            "images": [encoded_string]
        }
        
        logger.info(f"[IA-VISUAL] Analizando imagen {evidencia.id} con LLaVA...")
        resp = http_requests.post(ollama_url, json=payload, timeout=60)
        
        if resp.status_code == 200:
            analysis = resp.json().get('response', '').strip()
            evidencia.descripcion_ia = analysis
            evidencia.analizada = True
            evidencia.save(update_fields=['descripcion_ia', 'analizada'])
            
            logger.info(f"[IA-VISUAL] Imagen {evidencia.id} analizada exitosamente.")
            
            # 3. Forzar re-vectorización del ticket para incluir este nuevo contexto visual
            # Usar delay para no bloquear el worker de imágenes
            vectorize_ticket_n8n.delay(evidencia.ticket.id)
            
            return True
        else:
            logger.error(f"[IA-VISUAL] Error en Ollama: {resp.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"[IA-VISUAL] Error analizando imagen {evidencia_id}: {e}")
        return False

@shared_task(name='callcenter.tasks.sync_tickets_by_folio_list_task')
def sync_tickets_by_folio_list_task(folios_list):
    """
    Sincroniza múltiples tickets específicos por su folio.
    """
    username = os.environ.get('CALLCENTER_USER')
    password = os.environ.get('CALLCENTER_PASS')
    if not username or not password:
        return {"status": "error", "message": "Credenciales no configuradas."}
    company = "Centro Cívico Gubernamental de Honduras"
    
    from .scraper import download_tickets_by_folio_list
    from .utils import import_tickets_from_df
    
    try:
        download_dir = os.path.join(settings.BASE_DIR, 'downloads')
        files = download_tickets_by_folio_list(
            username=username,
            password=password,
            company_name=company,
            folios_list=folios_list,
            download_dir=download_dir
        )
        
        if not files:
            return {"status": "error", "message": "No se descargaron archivos de tickets."}
            
        dfs = []
        for f in files:
            if os.path.exists(f):
                dfs.append(pd.read_excel(f))
                # Limpieza opcional inmediata
                # os.remove(f)
        
        if not dfs:
            return {"status": "error", "message": "No se pudieron leer los archivos Excel."}
            
        combined_df = pd.concat(dfs, ignore_index=True)
        creados, actualizados = import_tickets_from_df(combined_df)
        
        return {"status": "success", "creados": creados, "actualizados": actualizados, "total_solicitados": len(folios_list)}
        
    except Exception as e:
        logger.error(f"Error en sync_tickets_by_folio_list_task: {e}")
        return {"status": "error", "message": str(e)}
