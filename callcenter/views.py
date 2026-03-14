from django.shortcuts import redirect
from django.contrib import messages
from .tasks import sync_tickets_task
from django.contrib.admin.views.decorators import staff_member_required
import logging
import json
import re
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import SolicitudTicket
from .utils import resolve_ticket_ubicacion
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from datetime import datetime
from django.http import HttpResponse, Http404, JsonResponse
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
import uuid
from playwright.sync_api import sync_playwright
logger = logging.getLogger(__name__)

@staff_member_required
def trigger_sync_tickets(request):
    """
    Vista para activar la sincronización de tickets de forma manual.
    """
    days = int(request.GET.get('days', 2))
    
    try:
        logger.info(f"[DEBUG] Despachando tarea sync_tickets_task para los últimos {days} días...")
        sync_tickets_task.delay(days=days)
        logger.info("[DEBUG] Tarea despachada correctamente a Celery.")
        messages.success(request, f"Se ha iniciado la sincronización de los últimos {days} días en segundo plano.")
    except Exception as e:
        logger.error(f"[ERROR] No se pudo enviar la tarea a Celery: {e}")
        messages.error(request, f"Error al iniciar la sincronización: {e}")
    
    # Redirigir al listado de tickets en el admin
    return redirect('admin:callcenter_solicitudticket_changelist')

@csrf_exempt
def webhook_new_ticket(request):
    """
    Endpoint para recibir tickets desde n8n/Power Automate.
    Identifica tickets primariamente por FOLIO.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        folio = data.get('folio', '').strip()
        
        if not folio:
            return JsonResponse({'error': 'Folio is required'}, status=400)
            
        # Extraer un ID numérico provisional del folio o del tiempo
        # Esto es necesario porque id_solicitud es campo obligatorio y único en BD
        # Si el ticket ya existe por Folio, usaremos su ID actual.
        # Si es nuevo, usaremos el numérico del folio o un timestamp negativo para indicar 'provisional'
        id_provisional = None
        match = re.search(r'(\d+)$', folio)
        if match:
            id_provisional = int(match.group(1))
        else:
            id_provisional = int(datetime.now().timestamp())

        # Buscar por Folio (Nuestra clave de verdad para webhooks)
        ticket = SolicitudTicket.objects.filter(folio=folio).first()
        
        target_id_solicitud = ticket.id_solicitud if ticket else id_provisional

        # Formatear fecha
        fecha_solicitud = None
        fecha_str = data.get('fecha')
        if fecha_str:
            try:
                dt = datetime.strptime(fecha_str, '%d/%m/%Y %H:%M:%S')
                fecha_solicitud = timezone.make_aware(dt)
            except:
                fecha_solicitud = timezone.now()

        # Resolver Ubicación
        loc_str = data.get('ubicacion_raw', '')
        edificio = ""
        nivel = ""
        if ' - ' in loc_str:
            parts = loc_str.split(' - ')
            edificio = parts[0].strip()
            nivel = parts[1].strip()
        elif loc_str:
            edificio = loc_str.strip()

        ubicacion_obj = resolve_ticket_ubicacion(edificio, nivel)

        # Crear o Actualizar Ticket usando id_solicitud como clave de integridad en DB
        # pero habiendo resuelto primero si el folio ya existía.
        ticket, created = SolicitudTicket.objects.update_or_create(
            id_solicitud=target_id_solicitud,
            defaults={
                'folio': folio,
                'solicitante': data.get('solicitante'),
                'solicitud_descripcion': data.get('descripcion'),
                'falla_descripcion': data.get('falla'),
                'servicio': data.get('servicio'),
                'subservicio': data.get('subservicio'),
                'nivel': edificio,
                'grupo': nivel,
                'ubicacion': ubicacion_obj,
                'fecha_solicitud': fecha_solicitud,
            }
        )

        return JsonResponse({
            'status': 'success',
            'action': 'created' if created else 'updated',
            'ticket_id': ticket.id,
            'folio': ticket.folio,
            'id_solicitud': ticket.id_solicitud
        })

    except Exception as e:
        logger.error(f"Error in webhook_new_ticket: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

from .scraper import sync_individual_ticket
import os

@staff_member_required
def sync_single_ticket(request, ticket_id):
    """
    Vista impulsada por el botón de "Sincronizar este Ticket" en el admin.
    """
    from .models import SolicitudTicket
    ticket = SolicitudTicket.objects.get(id=ticket_id)
    
    username = os.environ.get('CALLCENTER_USER')
    password = os.environ.get('CALLCENTER_PASS')
    company = "Centro Cívico Gubernamental de Honduras"

    if not username or not password:
        messages.error(request, "Credenciales (CALLCENTER_USER/PASS) no configuradas.")
        return redirect('admin:callcenter_solicitudticket_change', ticket_id)

    try:
        # Enviamos la tarea a Celery
        from .tasks import sync_single_ticket_task
        sync_single_ticket_task.delay(ticket_id)
        
        messages.info(request, f"Se ha iniciado la sincronización del ticket {ticket.folio} en segundo plano. El robot tardará unos segundos.")
            
    except Exception as e:
        messages.error(request, f"Error al enviar la tarea a Celery: {e}")

    return redirect('admin:callcenter_solicitudticket_change', ticket_id)

@csrf_exempt
def generate_ticket_pdf_view(request, folio):
    """
    Endpoint (API o Vista normal) para generar un archivo PDF 
    del reporte de un ticket, impulsado por N8n o Web.
    """
    ticket = SolicitudTicket.objects.filter(folio=folio).first()
    if not ticket:
        try:
            # Quizás folio contenga en realidad el ID
            ticket = SolicitudTicket.objects.filter(id_solicitud=int(folio)).first()
        except ValueError:
            pass

    if not ticket:
        raise Http404("El ticket no existe o no se encontró con ese folio.")

    base_url = request.build_absolute_uri('/').rstrip('/')
    html_content = render_to_string('callcenter/ticket_pdf.html', {'ticket': ticket, 'base_url': base_url}, request=request)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox', 
                    '--disable-setuid-sandbox', 
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )
            page = browser.new_page()
            page.set_content(html_content, wait_until='networkidle')
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                margin={'top': '20px', 'right': '20px', 'bottom': '20px', 'left': '20px'}
            )
            browser.close()

        # Guardar como Evidencia y en Storage MinIO
        file_name = f'comprobante_{ticket.folio or ticket.id_solicitud}_{uuid.uuid4().hex[:6]}.pdf'
        
        from callcenter.models import EvidenciaTicket
        evidencia = EvidenciaTicket.objects.create(
            ticket=ticket,
            descripcion="Comprobante de Cierre Generado Automáticamente"
        )
        evidencia.archivo.save(file_name, ContentFile(pdf_bytes))
        
        pdf_url = request.build_absolute_uri(evidencia.archivo.url)

        return JsonResponse({
            'success': True, 
            'url': pdf_url, 
            'folio': ticket.folio or ticket.id_solicitud
        })
    except Exception as e:
        logger.error(f"Error generando PDF del ticket {folio}: {str(e)}", exc_info=True)
import base64

@csrf_exempt
def webhook_evidencia_ticket(request, folio):
    """
    Endpoint (Webhook) para que n8n mande las imágenes que el usuario
    adjunta durante el proceso de cierre y poder guardarlas.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST allowed'}, status=405)

    try:
        ticket = SolicitudTicket.objects.filter(folio=folio).first()
        if not ticket:
            try:
                ticket = SolicitudTicket.objects.filter(id_solicitud=int(folio)).first()
            except ValueError:
                pass

        if not ticket:
            return JsonResponse({'error': 'Not found'}, status=404)

        data = json.loads(request.body)
        logger.info(f"Recibiendo webhook evidencia para ticket {folio}. Keys en data: {list(data.keys())}")
        
        # Explorar el payload de GoWA en N8N para buscar la base64
        body_data = data
        if 'body' in data:
            if isinstance(data['body'], dict):
                body_data = data['body']
            elif isinstance(data['body'], str):
                try:
                    body_data = json.loads(data['body'])
                except:
                    pass

        # Gowa payload suele traer { "message": "data:image/jpeg;base64,xxxxx..." }
        base64_str = ""
        for key in ['message', 'base64', 'body', 'data']:
            val = body_data.get(key)
            if isinstance(val, str) and 'base64,' in val:
                base64_str = val
                break
        
        if not base64_str and isinstance(body_data.get('payload'), dict):
            for key in ['message', 'base64', 'body', 'data']:
                val = body_data['payload'].get(key)
                if isinstance(val, str) and 'base64,' in val:
                    base64_str = val
                    break

        if base64_str and 'base64,' in base64_str:
            format, imgstr = base64_str.split('base64,') 
            ext = format.split('/')[-1].split(';')[0]
            if ext == 'jpeg': ext = 'jpg'
            
            file_name = f'foto_{ticket.folio or ticket.id_solicitud}_{uuid.uuid4().hex[:6]}.{ext}'
            
            data_bytes = base64.b64decode(imgstr)
            from callcenter.models import EvidenciaTicket
            evidencia = EvidenciaTicket.objects.create(ticket=ticket, descripcion='Adjunto desde WhatsApp', archivo=None)
            evidencia.archivo.save(file_name, ContentFile(data_bytes))
            
            return JsonResponse({'success': True, 'msg': 'Imagen guardada'})

        return JsonResponse({'success': False, 'msg': 'No base64 found'})
    except Exception as e:
        logger.error(f"Error parseando imagen: {e}", exc_info=True)
        return JsonResponse({'success': False, 'msg': str(e)}, status=500)

