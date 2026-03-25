from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .tasks import sync_tickets_task
from django.contrib.admin.views.decorators import staff_member_required
import logging
import json
import re
import uuid
import base64
import os
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse, Http404
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.utils import timezone
from playwright.sync_api import sync_playwright
from .models import SolicitudTicket, EvidenciaTicket
from .utils import resolve_ticket_ubicacion
import requests

logger = logging.getLogger(__name__)

def save_ticket_pdf_helper(ticket, request=None):
    """
    Helper para generar y guardar el PDF del ticket como una evidencia.
    Retorna la URL absoluta del PDF generado.
    """
    evidencias_b64 = []
    # Filtrar evidencias que no sean el propio PDF anterior
    desc_pdf_ignore = "Comprobante de Cierre Generado Automáticamente"
    qs_evidencias = EvidenciaTicket.objects.filter(ticket=ticket).exclude(descripcion=desc_pdf_ignore)
    
    for ev in qs_evidencias:
        if ev.archivo:
            try:
                img_bytes = ev.archivo.read()
                ext = ev.archivo.name.split('.')[-1].lower()
                mime = {
                    'png': 'image/png',
                    'webp': 'image/webp',
                    'gif': 'image/gif'
                }.get(ext, 'image/jpeg')
                
                b64 = base64.b64encode(img_bytes).decode('utf-8')
                evidencias_b64.append({
                    'data_uri': f'data:{mime};base64,{b64}', 
                    'descripcion': ev.descripcion or ''
                })
            except Exception as e:
                logger.warning(f"Error procesando imagen {ev.id} para PDF: {e}")

    # Cálculos adicionales
    tiempo_total = None
    if ticket.fecha_solicitud and ticket.fecha_cierre:
        diff = ticket.fecha_cierre - ticket.fecha_solicitud
        tiempo_total = int(diff.total_seconds() / 60)

    closed_by = ticket.responsable or 'ADMIN'
    if request and hasattr(request, 'GET'):
        closed_by = request.GET.get('closed_by', closed_by)

    # Encode logo
    logo_dcc_b64 = ""
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'activos', 'static', 'activos', 'img', 'logo_operadora_cc.png')
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as image_file:
            logo_dcc_b64 = base64.b64encode(image_file.read()).decode('utf-8')

    html_content = render_to_string('callcenter/ticket_pdf.html', {
        'ticket': ticket,
        'evidencias_b64': evidencias_b64,
        'tiempo_total': tiempo_total,
        'closed_by': closed_by,
        'ahora': timezone.now(),
        'logo_dcc_b64': logo_dcc_b64,
    }, request=request)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        page.set_content(html_content, wait_until='networkidle')
        pdf_bytes = page.pdf(format="A4", print_background=True)
        browser.close()

    desc_pdf = "Comprobante de Cierre Generado Automáticamente"
    file_name = f'comprobante_{ticket.folio or ticket.id_solicitud}_{uuid.uuid4().hex[:6]}.pdf'
    
    evidencia = EvidenciaTicket.objects.filter(ticket=ticket, descripcion=desc_pdf).first()
    if not evidencia:
        evidencia = EvidenciaTicket.objects.create(ticket=ticket, descripcion=desc_pdf)
    elif evidencia.archivo:
        try: evidencia.archivo.delete(save=False)
        except: pass
    
    evidencia.archivo.save(file_name, ContentFile(pdf_bytes))
    
    if request:
        return request.build_absolute_uri(evidencia.archivo.url)
    return evidencia.archivo.url

@staff_member_required
def trigger_sync_tickets(request):
    days = int(request.GET.get('days', 2))
    try:
        sync_tickets_task.delay(days=days)
        messages.success(request, f"Se ha iniciado la sincronización de los últimos {days} días en segundo plano.")
    except Exception as e:
        logger.error(f"Error al iniciar la sincronización: {e}")
        messages.error(request, f"Error al iniciar la sincronización: {e}")
    return redirect('admin:callcenter_solicitudticket_changelist')

def send_ticket_to_power_automate_view(request, ticket_id):
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
    
    # 0. Validación de campos obligatorios (Backend de seguridad)
    missing = []
    if not ticket.fecha_cierre: missing.append("Fecha Cierre")
    if not ticket.diagnostico: missing.append("Diagnóstico")
    if not ticket.actividades: missing.append("Actividades")
    if not ticket.observaciones: missing.append("Observaciones")
    
    if missing:
        messages.error(request, f"No se puede enviar el cierre. Faltan campos: {', '.join(missing)}")
        return redirect('admin:callcenter_solicitudticket_change', ticket_id)

    # 1. Generar/Actualizar PDF automáticamente antes de enviar
    try:
        pdf_url = save_ticket_pdf_helper(ticket, request=request)
    except Exception as e:
        logger.error(f"Error generando PDF para Power Automate: {e}")
        pdf_url = "Error en generación"

    # 2. Calcular Tiempo Total Min
    tiempo_total = 0
    if ticket.fecha_solicitud and ticket.fecha_cierre:
        diff = ticket.fecha_cierre - ticket.fecha_solicitud
        tiempo_total = int(diff.total_seconds() / 60)

    # 3. Formatear Fechas en Local para Power Automate
    def to_local_str(dt):
        if not dt: return ""
        local_dt = timezone.localtime(dt)
        return local_dt.strftime('%d/%m/%Y %H:%M:%S')

    # 4. Construir Payload (JSON Schema Exacto)
    payload = {
        "folio": str(ticket.folio or ticket.id_solicitud),
        "solicitante": str(ticket.solicitante or ""),
        "descripcion_original": (ticket.solicitud_descripcion or "").replace('\n', ' '),
        "falla": str(ticket.falla_descripcion or ""),
        "clasificacion_falla": str(ticket.falla_clasificacion or ""),
        "servicio": str(ticket.servicio or ""),
        "ubicacion": str(ticket.area or ""),
        "grupo_torre": str(ticket.nivel or ""),
        "nivel_piso": str(ticket.grupo or ""),
        "unidad_funcional": str(ticket.unidad or ""),
        "fecha_apertura": to_local_str(ticket.fecha_solicitud),
        "fecha_cierre": to_local_str(ticket.fecha_cierre),
        "diagnostico": (ticket.diagnostico or "").replace('\n', ' '),
        "actividades": (ticket.actividades or "").replace('\n', ' '),
        "observaciones": (ticket.observaciones or "").replace('\n', ' '),
        "pdf_url": str(pdf_url),
        "tiempo_total_min": int(tiempo_total),
        "cerrado_por_nombre": str(request.user.get_full_name() or request.user.username),
        "telefono_usuario": "Admin Panel",
        "email_usuario": str(request.user.email or "")
    }

    url_power_automate = "https://ce675e3ed2704594af019ed8d7d5f6.d7.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/6260ff428abe4f88b4cd96fae4614a57/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=IMrCwJsG1SsgYIYDKimFGYRkvxBFlg0MYpJWURimsLk"

    logger.info(f"Enviando Ticket {ticket.folio} a Power Automate (Admin)...")
    
    try:
        response = requests.post(url_power_automate, json=payload, timeout=30)
        if response.status_code in [200, 202]:
            ticket.cierre_enviado = True
            ticket.save(update_fields=['cierre_enviado'])
            messages.success(request, "Ticket enviado exitosamente a Power Automate.")
        else:
            messages.warning(request, f"Power Automate respondió con error {response.status_code}")
    except Exception as e:
        logger.error(f"Error conectando a Power Automate: {e}")
        messages.error(request, f"Error al conectar con Power Automate: {str(e)}")

    return redirect('admin:callcenter_solicitudticket_change', ticket_id)

@csrf_exempt
def webhook_new_ticket(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        folio = data.get('folio', '').strip()
        if not folio:
            return JsonResponse({'error': 'Folio is required'}, status=400)
        
        id_provisional = None
        match = re.search(r'(\d+)$', folio)
        if match:
            id_provisional = int(match.group(1))
        else:
            id_provisional = int(datetime.now().timestamp())

        ticket = SolicitudTicket.objects.filter(folio=folio).first()
        target_id_solicitud = ticket.id_solicitud if ticket else id_provisional

        fecha_solicitud = None
        fecha_str = data.get('fecha')
        if fecha_str:
            try:
                dt = datetime.strptime(fecha_str, '%d/%m/%Y %H:%M:%S')
                fecha_solicitud = timezone.make_aware(dt)
            except:
                fecha_solicitud = timezone.now()

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
        return JsonResponse({'status': 'success', 'folio': ticket.folio})
    except Exception as e:
        logger.error(f"Error in webhook_new_ticket: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def sync_single_ticket(request, ticket_id):
    from .tasks import sync_single_ticket_task
    sync_single_ticket_task.delay(ticket_id)
    messages.info(request, f"Se ha iniciado la sincronización en segundo plano.")
    return redirect('admin:callcenter_solicitudticket_change', ticket_id)

@csrf_exempt
def generate_ticket_pdf_view(request, folio):
    ticket = SolicitudTicket.objects.filter(folio=folio).first()
    if not ticket:
        try:
            ticket = SolicitudTicket.objects.filter(id_solicitud=int(folio)).first()
        except: pass
    if not ticket:
        raise Http404("Ticket no encontrado")

    evidencias_b64 = []
    for ev in ticket.evidencias.all():
        if ev.archivo and not ev.archivo.name.lower().endswith('.pdf'):
            try:
                # Asegurarse de leer los bytes correctamente
                with ev.archivo.open('rb') as f:
                    img_bytes = f.read()
                
                ext = ev.archivo.name.rsplit('.', 1)[-1].lower()
                mime = {
                    'jpg': 'image/jpeg', 
                    'jpeg': 'image/jpeg', 
                    'png': 'image/png',
                    'webp': 'image/webp'
                }.get(ext, 'image/jpeg')
                
                b64 = base64.b64encode(img_bytes).decode('utf-8')
                evidencias_b64.append({
                    'data_uri': f'data:{mime};base64,{b64}', 
                    'descripcion': ev.descripcion or ''
                })
            except Exception as e:
                logger.warning(f"Error procesando imagen {ev.id} para PDF: {e}")

    return save_ticket_pdf_helper(ticket, request=request)

@csrf_exempt
def webhook_evidencia_ticket(request, folio):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST allowed'}, status=405)
    try:
        ticket = SolicitudTicket.objects.filter(folio=folio).first()
        if not ticket:
            try: ticket = SolicitudTicket.objects.filter(id_solicitud=int(folio)).first()
            except: pass
        if not ticket: return JsonResponse({'error': 'Not found'}, status=404)

        # 1. Intentar por Archivo Directo (Multipart)
        if request.FILES:
            for field, file_obj in request.FILES.items():
                evidencia = EvidenciaTicket.objects.create(ticket=ticket, descripcion='Adjunto desde WhatsApp (Files)')
                ext = file_obj.name.split('.')[-1] if '.' in file_obj.name else 'jpg'
                file_name = f'foto_{ticket.folio or ticket.id_solicitud}_{uuid.uuid4().hex[:6]}.{ext}'
                evidencia.archivo.save(file_name, file_obj)
            return JsonResponse({'success': True, 'msg': 'Imagen guardada vía FILES'})

        # 2. Intentar por Cuerpo Binario Directo (n8n "Send Binary Data")
        # Si no es JSON y tiene longitud, y no hay FILES, probablemente es el binario crudo
        content_type = request.META.get('CONTENT_TYPE', '')
        if 'application/json' not in content_type and len(request.body) > 100:
            # Detectar formato por bytes mágicos
            ext = 'jpg'
            if request.body.startswith(b'\xff\xd8'): ext = 'jpg'
            elif request.body.startswith(b'\x89PNG'): ext = 'png'
            elif request.body.startswith(b'RIFF') and b'WEBP' in request.body[:15]: ext = 'webp'
            
            file_name = f'foto_{ticket.folio or ticket.id_solicitud}_{uuid.uuid4().hex[:6]}.{ext}'
            evidencia = EvidenciaTicket.objects.create(ticket=ticket, descripcion='Adjunto desde WhatsApp (Body)')
            evidencia.archivo.save(file_name, ContentFile(request.body))
            logger.info(f"Evidencia guardada vía BODY Raw: {file_name}")
            return JsonResponse({'success': True, 'msg': 'Imagen guardada vía Body'})

        # 3. Intentar por JSON (Base64)
        try:
            data = json.loads(request.body)
            def find_base64(obj):
                if isinstance(obj, str) and len(obj) > 100:
                    if 'base64,' in obj: return obj
                    try:
                        test = base64.b64decode(obj[:100], validate=False)
                        if test[:2] == b'\xff\xd8' or test[:4] == b'\x89PNG':
                            return f'data:image/jpeg;base64,{obj}'
                    except: pass
                elif isinstance(obj, dict):
                    for k in obj:
                        res = find_base64(obj[k])
                        if res: return res
                elif isinstance(obj, list):
                    for i in obj:
                        res = find_base64(i)
                        if res: return res
                return None

            b64_str = find_base64(data)
            if b64_str and 'base64,' in b64_str:
                format_part, imgstr = b64_str.split('base64,', 1)
                ext = format_part.split('/')[-1].split(';')[0] if '/' in format_part else 'jpg'
                if ext == 'jpeg': ext = 'jpg'
                file_name = f'foto_{ticket.folio or ticket.id_solicitud}_{uuid.uuid4().hex[:6]}.{ext}'
                evidencia = EvidenciaTicket.objects.create(ticket=ticket, descripcion='Adjunto desde WhatsApp (B64)')
                evidencia.archivo.save(file_name, ContentFile(base64.b64decode(imgstr)))
                return JsonResponse({'success': True, 'msg': 'Imagen guardada vía B64'})
        except: pass

        return JsonResponse({'success': False, 'msg': 'No image found', 'body_len': len(request.body)})
    except Exception as e:
        logger.error(f"Error parseando imagen: {e}", exc_info=True)
        return JsonResponse({'success': False, 'msg': str(e)}, status=500)


@staff_member_required
def ticket_search_view(request):
    """
    Buscador semántico de tickets usando embeddings vectoriales.
    Genera el embedding de la query usando Ollama y busca por distancia coseno.
    """
    from django.shortcuts import render
    from django.conf import settings
    import requests as http_requests
    
    query = request.GET.get('q', '').strip()
    resultados = []
    error = None
    
    if query:
        try:
            # 1. Generar embedding de la query usando Ollama
            ollama_url = f'{settings.OLLAMA_API_URL}/api/embeddings'
            
            resp = http_requests.post(ollama_url, json={
                'model': 'mxbai-embed-large',
                'prompt': query
            }, timeout=15)
            
            if resp.status_code != 200:
                error = f"Error al generar embedding: Ollama respondió {resp.status_code}"
            else:
                query_embedding = resp.json().get('embedding')
                if not query_embedding:
                    error = "Ollama no devolvió un embedding válido."
                else:
                    # 2. Buscar tickets similares
                    resultados = SolicitudTicket.buscar_vectorial(query_embedding, limit=15)
                    
        except http_requests.exceptions.ConnectionError:
            error = "No se pudo conectar con Ollama. Verifica que esté corriendo."
        except Exception as e:
            error = f"Error inesperado: {str(e)}"
            logger.error(f"Error en ticket_search_view: {e}", exc_info=True)
    
    return render(request, 'callcenter/buscar_tickets.html', {
        'query': query,
        'resultados': resultados,
        'error': error,
    })


@staff_member_required
def ticket_cierre_fiori_view(request, ticket_id):
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
    
    if request.method == 'POST':
        # AJAX Save Progress
        ticket.fecha_cierre = request.POST.get('fecha_cierre') or ticket.fecha_cierre
        ticket.diagnostico = request.POST.get('diagnostico', '')
        ticket.actividades = request.POST.get('actividades', '')
        ticket.observaciones = request.POST.get('observaciones', '')
        ticket.save()
        return JsonResponse({'success': True})

    evidences = EvidenciaTicket.objects.filter(ticket=ticket).order_by('-id')
    return render(request, 'callcenter/ticket_cierre_fiori.html', {
        'ticket': ticket,
        'evidences': evidences,
        'evidences_count': evidences.count(),
        'opts': SolicitudTicket._meta,
    })

@csrf_exempt
@staff_member_required
def upload_evidencia_ajax(request, ticket_id):
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
    if request.method == 'POST' and request.FILES:
        files = request.FILES.getlist('files')
        for f in files:
            evidencia = EvidenciaTicket.objects.create(
                ticket=ticket, 
                descripcion=f"Foto Fiori {datetime.now().strftime('%H:%M')}"
            )
            # Extraer extensión y generar nombre único
            ext = f.name.split('.')[-1] if '.' in f.name else 'jpg'
            file_name = f'fiori_{ticket.id}_{uuid.uuid4().hex[:6]}.{ext}'
            evidencia.archivo.save(file_name, f)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@csrf_exempt
@staff_member_required
def delete_evidencia_ajax(request, ticket_id, evidencia_id):
    evidencia = get_object_or_404(EvidenciaTicket, id=evidencia_id, ticket_id=ticket_id)
    if request.method == 'POST':
        evidencia.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)
