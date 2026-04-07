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
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse, Http404
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.utils import timezone
from playwright.sync_api import sync_playwright
from .models import SolicitudTicket, EvidenciaTicket
from .utils import resolve_ticket_ubicacion
import requests
from core.models import PerfilUsuario
from django.conf import settings

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

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            page.set_content(html_content, wait_until='networkidle')
            pdf_bytes = page.pdf(format="A4", print_background=True)
            browser.close()
    except Exception as e:
        logger.error(f"Error crítico en Playwright al generar PDF para ticket {ticket.id}: {e}")
        # Retornar algo que indique error o relanzar si es fatal para la vista
        raise e

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

    # 3.5 Recolectar emails del departamento del usuario que cierra
    emails_departamento = ""
    try:
        perfil = PerfilUsuario.objects.select_related('departamento').filter(usuario=request.user).first()
        if perfil and perfil.departamento:
            depto = perfil.departamento
            # Emails de todos los integrantes del departamento
            emails_list = list(
                PerfilUsuario.objects.filter(departamento=depto)
                .exclude(usuario__email='')
                .exclude(usuario__email__isnull=True)
                .values_list('usuario__email', flat=True)
            )
            # Agregar email del jefe/responsable del departamento si existe
            if depto.responsable and depto.responsable.email:
                if depto.responsable.email not in emails_list:
                    emails_list.append(depto.responsable.email)
            emails_departamento = ";".join(emails_list)
            logger.info(f"Emails del departamento '{depto.nombre}': {emails_departamento}")
    except Exception as e:
        logger.warning(f"Error obteniendo emails del departamento: {e}")
        emails_departamento = str(request.user.email or "")

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
        "email_usuario": str(request.user.email or ""),
        "emails_departamento": emails_departamento
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

    # Delegar la generación y guardado al helper
    try:
        pdf_url = save_ticket_pdf_helper(ticket, request=request)
        return redirect(pdf_url)
    except Exception as e:
        logger.error(f"Error al generar PDF para el folio {folio}: {e}")
        return HttpResponse("Error interno al generar el PDF. Por favor, verifique los logs del servidor.", status=500)

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
def ticket_cierre_visual_view(request, ticket_id):
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
    
    if request.method == 'POST':
        # AJAX Save Progress
        ticket.fecha_cierre = request.POST.get('fecha_cierre') or ticket.fecha_cierre
        ticket.diagnostico = request.POST.get('diagnostico', '')
        ticket.actividades = request.POST.get('actividades', '')
        ticket.observaciones = request.POST.get('observaciones', '')
        
        # Nuevos campos: Deductiva y Proveedor
        deductiva_val = request.POST.get('deductiva', '0')
        try:
            from decimal import Decimal
            ticket.deductiva = Decimal(deductiva_val.replace(',', ''))
        except:
            pass
            
        proveedor_id = request.POST.get('proveedor_deductiva')
        if proveedor_id:
            from mantenimiento.models import Empresa
            ticket.proveedor_deductiva = Empresa.objects.filter(id=proveedor_id).first()
        else:
            ticket.proveedor_deductiva = None
            
        ticket.save()
        return JsonResponse({'success': True})

    evidences = EvidenciaTicket.objects.filter(ticket=ticket).order_by('-id')
    from mantenimiento.models import Empresa
    proveedores = Empresa.objects.filter(activo=True).order_by('nombre')
    
    return render(request, 'callcenter/ticket_cierre_visual.html', {
        'ticket': ticket,
        'evidences': evidences,
        'evidences_count': evidences.count(),
        'proveedores': proveedores,
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
                descripcion=f"Foto Evidencia {datetime.now().strftime('%H:%M')}"
            )
            # Extraer extensión y generar nombre único
            ext = f.name.split('.')[-1] if '.' in f.name else 'jpg'
            file_name = f'evidencia_{ticket.id}_{uuid.uuid4().hex[:6]}.{ext}'
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

@csrf_exempt
@staff_member_required
def update_evidencia_descripcion_ajax(request, evidence_id):
    if request.method == 'POST':
        from .models import EvidenciaTicket
        evidencia = get_object_or_404(EvidenciaTicket, id=evidence_id)
        descripcion = request.POST.get('descripcion', '')
        evidencia.descripcion = descripcion
        evidencia.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@staff_member_required
def ticket_dashboard_view(request):
    """
    Dashboard principal de tickets y grupos (clusters).
    """
    from .models import SolicitudTicket, GrupoTicket
    from django.db.models import Count, Q
    
    # Métricas Globales
    total_tickets = SolicitudTicket.objects.count()
    tickets_cerrados = SolicitudTicket.objects.filter(
        Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True)
    ).count()
    tickets_abiertos = total_tickets - tickets_cerrados
    
    # Grupos Recientes con conteo de tickets y estadísticas de cierre
    from django.db.models import Prefetch, Count, Q
    grupos = GrupoTicket.objects.annotate(
        num_tickets=Count('tickets'),
        num_cerrados=Count('tickets', filter=Q(tickets__fecha_cierre__isnull=False) | Q(tickets__cierre_enviado=True)),
        num_abiertos=Count('tickets', filter=Q(tickets__fecha_cierre__isnull=True) & Q(tickets__cierre_enviado=False))
    ).order_by('-fecha')[:12]
    
    context = {
        'total': total_tickets,
        'cerrados': tickets_cerrados,
        'abiertos': tickets_abiertos,
        'grupos': grupos,
        'title': 'Dashboard de Tickets'
    }
    return render(request, 'callcenter/ticket_dashboard.html', context)

@staff_member_required
def cluster_tickets_view(request, cluster_id):
    """
    Lista todos los tickets de un grupo (cluster) específico con diseño Visual.
    Incluye estadísticas y exportación a Excel/PDF.
    """
    from .models import GrupoTicket
    from django.db.models import Q
    import pandas as pd
    from xhtml2pdf import pisa
    
    from django.db.models import Prefetch, Count, Q
    cluster = get_object_or_404(GrupoTicket, id=cluster_id)
    
    # Optimizamos agregando el conteo de tiempos acordados asociados
    tickets = cluster.tickets.all().select_related(
        'ubicacion', 'usuario_responsable'
    ).annotate(
        num_tiempos_acordados=Count('tiempos_acordados')
    ).order_by('-fecha_solicitud')
    
    # Calcular estadísticas dirigidas (siempre sobre el total del cluster)
    total = tickets.count()
    cerrados = tickets.filter(Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True)).count()
    abiertos = total - cerrados

    # Búsqueda por folio o descripción
    q = request.GET.get('q', '').strip()
    if q:
        tickets = tickets.filter(
            Q(folio__icontains=q) | 
            Q(solicitud_descripcion__icontains=q) | 
            Q(id_solicitud__icontains=q) |
            Q(responsable__icontains=q) |
            Q(usuario_responsable__first_name__icontains=q) |
            Q(usuario_responsable__last_name__icontains=q)
        ).distinct()
    
    # Filtrado por status
    status_filter = request.GET.get('status')
    if status_filter == 'abiertos':
        tickets = tickets.filter(Q(fecha_cierre__isnull=True) & Q(cierre_enviado=False))
    elif status_filter == 'cerrados':
        tickets = tickets.filter(Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True))

    # Ordenar por estado
    sort = request.GET.get('sort')
    if sort == 'estado':
        from django.db.models import Case, When, Value, IntegerField
        tickets = tickets.annotate(
            is_closed=Case(
                When(Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True), then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).order_by('is_closed', '-fecha_solicitud')
    elif sort == '-estado':
        from django.db.models import Case, When, Value, IntegerField
        tickets = tickets.annotate(
            is_closed=Case(
                When(Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True), then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).order_by('-is_closed', '-fecha_solicitud')
    
    # Manejo de Exportación
    export_type = request.GET.get('export')
    
    if export_type == 'excel':
        data = []
        for t in tickets:
            data.append({
                'Folio/ID': t.folio or t.id_solicitud,
                'Solicitante': t.solicitante,
                'Resp. Solicitud': t.responsable or '-',
                'Técnico Asignado': t.usuario_responsable.get_full_name() if t.usuario_responsable else 'Sin Asignar',
                'Descripción': t.solicitud_descripcion,
                'Fecha Solicitud': t.fecha_solicitud.strftime('%d/%m/%Y %H:%M') if t.fecha_solicitud else '',
                'Estado': 'Cerrado' if (t.fecha_cierre or t.cierre_enviado) else 'Abierto'
            })
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="Reporte_Cluster_{cluster.correlativo}.xlsx"'
        df.to_excel(response, index=False)
        return response

    if export_type == 'pdf':
        html_content = render_to_string('callcenter/cluster_report_pdf.html', {
            'cluster': cluster,
            'tickets': tickets,
            'total': total,
            'cerrados': cerrados,
            'abiertos': abiertos,
            'fecha_reporte': timezone.now()
        })
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Reporte_Cluster_{cluster.correlativo}.pdf"'
        pisa_status = pisa.CreatePDF(html_content, dest=response)
        if pisa_status.err:
            return HttpResponse('Error al generar PDF', status=500)
        return response

    context = {
        'cluster': cluster,
        'tickets': tickets,
        'abiertos': abiertos,
        'cerrados': cerrados,
        'total': total,
        'q': q,
        'title': f"Tickets en {cluster.correlativo}"
    }
    return render(request, 'callcenter/cluster_tickets.html', context)

@staff_member_required
def get_assignable_users_ajax(request):
    """Devuelve diccionario de usuarios activos para el SweetAlert2 select."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    users = User.objects.filter(is_active=True).order_by('first_name', 'username')
    results = {}
    for u in users:
        results[str(u.id)] = u.get_full_name() or u.username
    return JsonResponse(results)

@staff_member_required
@require_POST
@csrf_exempt
def assign_ticket_user_ajax(request, ticket_id):
    """Asigna un usuario responsable a un ticket via AJAX."""
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
    
    import json
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
    except (json.JSONDecodeError, AttributeError):
        user_id = request.POST.get('user_id')
    
    if user_id:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = get_object_or_404(User, id=user_id)
        ticket.usuario_responsable = user
    else:
        ticket.usuario_responsable = None
        
    ticket.save()
    
    name = ticket.usuario_responsable.get_full_name() or ticket.usuario_responsable.username if ticket.usuario_responsable else 'Sin asignar'
    return JsonResponse({'success': True, 'name': name})

@staff_member_required
def search_activos_ajax(request):
    """Buscador de activos por nombre, código interno, serie o epc."""
    q = request.GET.get('q', '').strip()
    if len(q) < 3:
        return JsonResponse({'results': []})
    
    from activos.models.activo import Activo
    from django.db.models import Q
    
    activos = Activo.objects.filter(
        Q(nombre__icontains=q) |
        Q(codigo_interno__icontains=q) |
        Q(serie__icontains=q) |
        Q(epc__icontains=q)
    ).select_related('modelo', 'modelo__marca')[:20]
    
    results = []
    for a in activos:
        results.append({
            'id': a.id,
            'nombre': a.nombre,
            'codigo': a.codigo_interno,
            'serie': a.serie or 'N/S',
            'marca': a.modelo.marca.nombre if (a.modelo and a.modelo.marca) else 'N/A',
            'modelo': a.modelo.nombre if a.modelo else 'N/A',
        })
    
    return JsonResponse({'results': results})

@staff_member_required
@csrf_exempt
def update_ticket_activo_ajax(request, ticket_id):
    """Vincula un activo a un ticket en tiempo real."""
    if request.method == 'POST':
        ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
        activo_id = request.POST.get('activo_id')
        
        if activo_id:
            from activos.models.activo import Activo
            activo = get_object_or_404(Activo, id=activo_id)
            ticket.activo = activo
        else:
            ticket.activo = None
            
        ticket.save(update_fields=['activo'])
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)
@staff_member_required
@require_POST
def notify_ticket_n8n_ajax(request, ticket_id):
    """Envía los datos del ticket a n8n para notificaciones (WhatsApp, etc)."""
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
    
    # Obtener el teléfono del técnico asignado si existe
    phone = "Sin teléfono"
    tech_name = "Sin asignar"
    
    if ticket.usuario_responsable:
        tech_name = ticket.usuario_responsable.get_full_name() or ticket.usuario_responsable.username
        # Intentar obtener perfil para el teléfono
        perfil = PerfilUsuario.objects.filter(usuario=ticket.usuario_responsable).first()
        if perfil and perfil.telefono:
            phone = perfil.telefono

    # Payload para n8n
    payload = {
        "event": "ticket_notification_manual",
        "ticket_id": ticket.id,
        "folio": ticket.folio or str(ticket.id_solicitud),
        "solicitante": ticket.solicitante,
        "responsable_texto": ticket.responsable, # El campo de texto original
        "tecnico_asignado": tech_name,
        "tecnico_telefono": phone,
        "descripcion": ticket.solicitud_descripcion,
        "ubicacion": str(ticket.ubicacion) if ticket.ubicacion else "No definida",
        "servicio": ticket.servicio,
        "fecha_solicitud": ticket.fecha_solicitud.strftime('%d/%m/%Y %H:%M') if ticket.fecha_solicitud else "N/A",
        "url_dashboard": request.build_absolute_uri(f"/callcenter/dashboard/cluster/{ticket.grupos.first().id}/") if ticket.grupos.exists() else ""
    }

    try:
        webhook_url = getattr(settings, 'N8N_TICKET_NOTIFY_URL', None)
        if not webhook_url:
            return JsonResponse({'success': False, 'error': 'Webhook URL no configurada en settings.'})

        response = requests.post(webhook_url, json=payload, timeout=10)
        
        if response.ok:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': f'n8n respondió con error: {response.status_code}'})
            
    except Exception as e:
        logger.error(f"Error enviando notificación a n8n: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@staff_member_required
def mobile_detalle_tiempo_acordado_view(request, pk):
    """Vista Fiori para ver el detalle de un Tiempo Acordado desde la App."""
    from .models import TiempoAcordado, TiempoAcordadoTarea
    from django.shortcuts import get_object_or_404
    
    from django.utils import timezone
    from datetime import timedelta
    
    acuerdo = get_object_or_404(TiempoAcordado, pk=pk)
    tareas = acuerdo.tareas.all().order_by('fecha_inicio')
    
    # Cálculos para Diagrama de Gantt con manejo de zonas horarias
    total_start = acuerdo.creado_en
    if total_start and timezone.is_naive(total_start):
        total_start = timezone.make_aware(total_start)
        
    if tareas.exists():
        first_start = tareas.first().fecha_inicio
        if first_start:
            if timezone.is_naive(first_start):
                first_start = timezone.make_aware(first_start)
            if first_start < total_start:
                total_start = first_start
            
    total_end = acuerdo.fecha_solucion_final
    if total_end and timezone.is_naive(total_end):
        total_end = timezone.make_aware(total_end)
    
    # Asegurar que total_end sea posterior a total_start
    if not total_end or total_end <= total_start:
        total_end = total_start + timedelta(hours=1)
        
    total_seconds = (total_end - total_start).total_seconds()
    
    # Si por algún motivo la duración es 0, evadir error
    if total_seconds <= 0:
        total_seconds = 1
        
    for tarea in tareas:
        t_start = tarea.fecha_inicio
        t_end = tarea.fecha_fin
        
        if t_start and timezone.is_naive(t_start): t_start = timezone.make_aware(t_start)
        if t_end and timezone.is_naive(t_end): t_end = timezone.make_aware(t_end)
        
        if t_start and t_end and total_seconds > 0:
            tarea.left_percent = (t_start - total_start).total_seconds() / total_seconds * 100
            tarea.width_percent = (t_end - t_start).total_seconds() / total_seconds * 100
        else:
            tarea.left_percent = 0
            tarea.width_percent = 0
            
        # Evitar anchos 0 para que siempre se vea un punto al menos
        if tarea.width_percent < 1:
            tarea.width_percent = 2
            
    # Título seguro
    try:
        if acuerdo.ticket:
            ticket_label = acuerdo.ticket.folio or acuerdo.ticket.id_solicitud
        else:
            ticket_label = f"ID:{acuerdo.id}"
    except:
        ticket_label = str(acuerdo.id)

    context = {
        'acuerdo': acuerdo,
        'tareas': tareas,
        'total_start': total_start,
        'total_end': total_end,
        'title': f'Acuerdo: {ticket_label}'
    }
    return render(request, 'callcenter/mobile_detalle_tiempo_acordado.html', context)


def _generate_tiempo_acordado_pdf_binary(acuerdo):
    """
    Función interna que centraliza la generación del reporte.
    Retorna una tupla: (archivo_bytes, nombre_archivo, content_type)
    """
    from django.utils.dateformat import format as django_date_format
    from django.conf import settings
    from docxtpl import DocxTemplate, InlineImage
    from docx.shared import Mm
    import os
    import io
    import tempfile
    import uuid
    import math
    from PIL import Image, ImageDraw, ImageFont

    from django.utils import timezone
    
    tareas = acuerdo.tareas.all().order_by('fecha_inicio')
    
    total_start = acuerdo.creado_en
    if total_start and timezone.is_naive(total_start):
        total_start = timezone.make_aware(total_start)
        
    if tareas.exists():
        first_start = tareas.first().fecha_inicio
        if first_start:
            if timezone.is_naive(first_start):
                first_start = timezone.make_aware(first_start)
            if first_start < total_start:
                total_start = first_start
            
    total_end = acuerdo.fecha_solucion_final
    total_seconds = (total_end - total_start).total_seconds()
    if total_seconds <= 0: total_seconds = 1
        
    total_duration_days = total_seconds / 86400.0
    if total_duration_days < 1: total_duration_days = 1

    if total_duration_days <= 12: step = 1
    elif total_duration_days <= 25: step = 2
    elif total_duration_days <= 50: step = 5
    elif total_duration_days <= 100: step = 10
    else:
        raw_step = total_duration_days / 8.0
        step = int(math.ceil(raw_step / 10.0)) * 10
    
    day_markers = []
    curr = 0
    while curr <= total_duration_days:
        day_markers.append(int(curr))
        curr += step
    if day_markers[-1] < total_duration_days:
        day_markers.append(day_markers[-1] + step)
        
    visual_max_days = day_markers[-1]
    visual_max_seconds = visual_max_days * 86400.0
    
    def generate_gantt_image_stream():
        w, row_h, head_h, foot_h = 1600, 60, 60, 40
        h = head_h + (len(tareas) * row_h) + foot_h
        img = Image.new('RGB', (w, h), color="#ffffff")
        draw = ImageDraw.Draw(img)
        
        try: font_bold = ImageFont.truetype("arialbd.ttf", 26)
        except: font_bold = ImageFont.load_default()
        try: font = ImageFont.truetype("arial.ttf", 24)
        except: font = ImageFont.load_default()
        try: font_small = ImageFont.truetype("arial.ttf", 22)
        except: font_small = ImageFont.load_default()
        
        title_w = 500
        gantt_w = w - title_w - 40
        gantt_x = title_w + 20
        
        m_step = gantt_w / max(1, len(day_markers)-1)
        
        # --- NUEVO: RELLENO DE CABECERA Y TITULOS ---
        # Relleno cabecera (Días)
        draw.rectangle([0, 0, w, head_h], fill="#f2f5f9")
        # Relleno columna títulos (Actividades)
        draw.rectangle([0, 0, title_w, h], fill="#fdfdfd")
        
        for i, m in enumerate(day_markers):
            x = gantt_x + (i * m_step)
            draw.line([(x, head_h), (x, h - foot_h)], fill="#e0e0e0", width=2)
            draw.text((x - 20, (head_h-24)/2), f"Día {m}", fill="#34495e", font=font_small)
            
        draw.line([(0, head_h), (w, head_h)], fill="#d5d8dc", width=3)
        draw.line([(title_w, 0), (title_w, h)], fill="#d5d8dc", width=3)
        
        for i, t in enumerate(tareas):
            y = head_h + (i * row_h)
            desc = (t.descripcion[:50] + '..') if len(t.descripcion) > 50 else t.descripcion
            text_bbox = draw.textbbox((0, 0), desc.upper(), font=font_bold)
            text_w = text_bbox[2] - text_bbox[0]
            draw.text((title_w - text_w - 15, y + (row_h-24)/2), desc.upper(), fill="#000000", font=font_bold)
            draw.line([(title_w, y + row_h), (w, y + row_h)], fill="#e0e0e0", width=2)
            
            lp = (t.fecha_inicio - total_start).total_seconds() / visual_max_seconds
            wp = (t.fecha_fin - t.fecha_inicio).total_seconds() / visual_max_seconds
            
            bx = gantt_x + (lp * gantt_w)
            bw = max(wp * gantt_w, 10)
            by1, by2 = y + 12, y + row_h - 12
            
            # Sombra de la barra
            draw.rectangle([bx+3, by1+3, bx+bw+3, by2+3], fill="#d5d8dc")
            # Barra principal
            draw.rectangle([bx, by1, bx + bw, by2], fill="#2e86c1")
            
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    # --- LOGICA: GENERACIÓN DOCX USANDO DOCXTPL ---
    template_path = os.path.join(settings.BASE_DIR, 'tiempo_acordado_template.docx')
    if os.path.exists(template_path):
        doc = DocxTemplate(template_path)
        gantt_stream = generate_gantt_image_stream() if tareas.exists() else None
        
        def get_base64_image_tag(base64_str, label=""):
            if not base64_str:
                logger.debug(f"Firma {label} está vacía.")
                return ""
            
            try:
                if "base64," in base64_str:
                    base64_str = base64_str.split("base64,")[-1]
                
                base64_str = base64_str.replace('\n', '').replace('\r', '').replace(' ', '')
                # Usar el import global
                import base64 as b64_lib
                image_data = b64_lib.b64decode(base64_str)
                
                # RE-PROCESAMIENTO CON PIL
                from PIL import Image
                img_input = Image.open(io.BytesIO(image_data))
                
                # CREAR FONDO BLANCO (Flattening)
                # Esto soluciona problemas de transparencia en Word
                new_img = Image.new("RGB", img_input.size, (255, 255, 255))
                if img_input.mode == 'RGBA':
                    new_img.paste(img_input, (0, 0), img_input)
                else:
                    new_img.paste(img_input, (0, 0))
                
                buf = io.BytesIO()
                new_img.save(buf, format="JPEG", quality=95) # JPEG es más seguro para Word flat
                buf.seek(0)
                
                img_tag = InlineImage(doc, buf, width=Mm(50))
                logger.info(f"Firma {label} re-procesada (Flattened) exitosamente. Orientación: {img_input.size}")
                return img_tag
            except Exception as e:
                logger.error(f"Error procesando firma {label} para Word: {e}")
                return ""

        ctx = {
            'FOLIO': acuerdo.ticket.folio or acuerdo.ticket.id_solicitud,
            'ENLACE_MAO': acuerdo.enlace.nombre if acuerdo.enlace else '',
            'FECHA_SOLICITUD': django_date_format(acuerdo.ticket.fecha_solicitud, "l d/m/Y g:i a") if acuerdo.ticket.fecha_solicitud else '',
            'INSTITUCION': acuerdo.institucion.nombre if acuerdo.institucion else '',
            'UBICACION': acuerdo.ticket.area or "Cuerpo bajo A Nivel 4",
            'FECHA_SOLUCION': django_date_format(acuerdo.fecha_solucion_final, "l d/m/Y g:i a") if acuerdo.fecha_solucion_final else '',
            'MOTIVO': acuerdo.motivo_extension or '',
            'SOLUCION_PROVISIONAL': acuerdo.solucion_provisional or 'Se implementó solución de mitigación provisoria.',
            'OBSERVACIONES': acuerdo.observaciones or '',
            'GANTT': InlineImage(doc, gantt_stream, width=Mm(190)) if gantt_stream else "",
            # Tags principales
            'FIRMA_RESPONSABLE': get_base64_image_tag(acuerdo.firma_responsable, "RESPONSABLE"),
            'FIRMA_ENLACE': get_base64_image_tag(acuerdo.firma_enlace, "ENLACE"),
            # Variaciones por si la plantilla usa nombres cortos
            'firma_resp': get_base64_image_tag(acuerdo.firma_responsable, "RESPONSABLE_V"),
            'firma_enl': get_base64_image_tag(acuerdo.firma_enlace, "ENLACE_V"),
            'FIRMA_R': get_base64_image_tag(acuerdo.firma_responsable, "RESPONSABLE_V2")
        }

        doc.render(ctx)
        
        # 1. Guardar DOCX temporal
        temp_dir = tempfile.gettempdir()
        temp_docx = os.path.join(temp_dir, f"{uuid.uuid4()}.docx")
        temp_pdf = temp_docx.replace(".docx", ".pdf")
        doc.save(temp_docx)

        # 2. Intentar conversión con LibreOffice (LibreOffice debe estar en el servidor)
        import subprocess
        try:
            # Comando estándar para Linux: soffice --headless --convert-to pdf --outdir <dir> <archivo>
            subprocess.run([
                'soffice', '--headless', '--convert-to', 'pdf',
                '--outdir', temp_dir, temp_docx
            ], check=True, capture_output=True, timeout=30)
            
            if os.path.exists(temp_pdf):
                with open(temp_pdf, "rb") as f:
                    data = f.read()
                os.remove(temp_docx)
                os.remove(temp_pdf)
                logger.info(f"PDF de Tiempo Acordado {acuerdo.id} generado exitosamente vía LibreOffice.")
                return data, f"Acuerdo_Tiempo_Acordado_{acuerdo.id}.pdf", "application/pdf"
        except Exception as e:
            logger.warning(f"Fallo conversión LibreOffice para acuerdo {acuerdo.id}: {e}")
            pass 

        # 3. Intentar conversión con docx2pdf (Solo funciona en Windows)
        try:
            from docx2pdf import convert as docx2pdf_convert
            import pythoncom
            pythoncom.CoInitialize()
            docx2pdf_convert(temp_docx, temp_pdf)
            
            if os.path.exists(temp_pdf):
                with open(temp_pdf, "rb") as f:
                    data = f.read()
                os.remove(temp_docx)
                os.remove(temp_pdf)
                logger.info(f"PDF de Tiempo Acordado {acuerdo.id} generado exitosamente vía docx2pdf (Windows).")
                return data, f"Acuerdo_Tiempo_Acordado_{acuerdo.id}.pdf", "application/pdf"
        except Exception as e:
            logger.warning(f"Fallo conversión docx2pdf para acuerdo {acuerdo.id}: {e}")
            pass

        # 4. ÚLTIMO RECURSO: PDF vía HTML (Si todo lo de Word falla o no está disponible)
        from django.template.loader import render_to_string
        from playwright.sync_api import sync_playwright
        import base64 as b64_lib
        
        gantt_b64 = ""
        if tareas.exists():
            gantt_buf = generate_gantt_image_stream()
            gantt_b64 = b64_lib.b64encode(gantt_buf.getvalue()).decode('utf-8')
        
        # Limpiar firmas para asegurar que el navegador las lea correctamente
        firma_r = acuerdo.firma_responsable or ""
        firma_e = acuerdo.firma_enlace or ""
        
        # Asegurar prefijo data:image si falta (ya que Playwright lo necesita en el tag img)
        if firma_r and not firma_r.startswith('data:'): firma_r = f"data:image/png;base64,{firma_r}"
        if firma_e and not firma_e.startswith('data:'): firma_e = f"data:image/png;base64,{firma_e}"
        
        html_context = {
            'acuerdo': acuerdo, 
            'gantt_b64': gantt_b64,
            'firma_r': firma_r,
            'firma_e': firma_e
        }
        html_string = render_to_string('callcenter/tiempo_acordado_pdf.html', html_context)
        logger.info(f"Generando PDF de Tiempo Acordado {acuerdo.id} vía Playwright (Fallback de alta fidelidad).")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
                page = browser.new_page()
                page.set_content(html_string, wait_until='networkidle')
                pdf_bytes = page.pdf(format="A4", print_background=True, margin={'top': '1cm', 'bottom': '1cm', 'left': '1cm', 'right': '1cm'})
                browser.close()
                os.remove(temp_docx)
                return pdf_bytes, f"Acuerdo_Tiempo_Acordado_{acuerdo.id}.pdf", "application/pdf"
        except Exception as e:
            logger.error(f"Fallo crítico en Playwright Fallback para acuerdo {acuerdo.id}: {e}")
            # Si falla Playwright, intentar mandar al menos el DOCX
            with open(temp_docx, "rb") as f:
                data = f.read()
            os.remove(temp_docx)
            return data, f"Acuerdo_Tiempo_Acordado_{acuerdo.id}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        # 5. RETORNO DE EMERGENCIA: Mandar el DOCX si nada pudo hacer el PDF
        with open(temp_docx, "rb") as f:
            data = f.read()
        os.remove(temp_docx)
        return data, f"Acuerdo_Tiempo_Acordado_{acuerdo.id}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # Si ni siquiera existe el template de Word, retornar error vacío (pero no debería pasar)
    return b"", "error.txt", "text/plain"

    # Si ni siquiera existe el template de Word, retornar error vacío (pero no debería pasar)
    return b"", "error.txt", "text/plain"

def exportar_tiempo_acordado_pdf_view(request, pk):
    """Vista de descarga directa del PDF."""
    from .models import TiempoAcordado
    from django.shortcuts import get_object_or_404
    from django.http import HttpResponse

    acuerdo = get_object_or_404(TiempoAcordado, pk=pk)
    data, filename, content_type = _generate_tiempo_acordado_pdf_binary(acuerdo)
    
    response = HttpResponse(data, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@staff_member_required
def enviar_tiempo_acordado_power_automate_ajax(request, pk):
    """Genera el reporte e invoca el flujo de Power Automate."""
    from .models import TiempoAcordado
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse
    import requests
    import base64
    import json

    acuerdo = get_object_or_404(TiempoAcordado, pk=pk)
    
    try:
        # 1. Generar el binario
        data, filename, content_type = _generate_tiempo_acordado_pdf_binary(acuerdo)
        pdf_base64 = base64.b64encode(data).decode('utf-8')

        # 2. Preparar el contenido del correo (HTML)
        acuerdo_folio = acuerdo.ticket.folio or acuerdo.ticket.id_solicitud
        subject = f"Reporte: Acuerdo de Tiempo - Ticket {acuerdo_folio}"
        
        email_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; margin: 0; padding: 20px; background-color: #f4f6f9;">
            <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 8px; border-top: 5px solid #0070f2; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h2 style="color: #0070f2; margin-bottom: 20px;">Acuerdo de Tiempo y Solución Provisional</h2>
                <p>Se ha generado un nuevo acuerdo para el ticket <b>{acuerdo_folio}</b>.</p>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold; width: 40%;">Institución:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{acuerdo.institucion.nombre if acuerdo.institucion else '-'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Enlace MAO:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{acuerdo.enlace.nombre if acuerdo.enlace else '-'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Fecha Solución Final:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee; color: #d32f2f;">{acuerdo.fecha_solucion_final.strftime('%d/%m/%Y %I:%M %p') if acuerdo.fecha_solucion_final else '-'}</td>
                    </tr>
                </table>
                <p style="margin-top: 20px;">Por favor, encuentre adjunto el reporte detallado en formato PDF.</p>
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #777;">
                    Este es un correo automático generado por el sistema <b>SoftCom Energy</b>.
                </div>
            </div>
        </body>
        </html>
        """

        # 3. Construir Payload
        payload = {
            "folio": acuerdo_folio,
            "institucion": acuerdo.institucion.nombre if acuerdo.institucion else "N/A",
            "enlace": acuerdo.enlace.nombre if acuerdo.enlace else "N/A",
            "correo_enlace": acuerdo.enlace.email if acuerdo.enlace and acuerdo.enlace.email else "",
            "correo_usuario": request.user.email if request.user.email else request.user.username,
            "fecha_compromiso": acuerdo.fecha_solucion_final.strftime("%d/%m/%Y %H:%M") if acuerdo.fecha_solucion_final else "N/A",
            "motivo": acuerdo.motivo_extension or "",
            "subject": subject,
            "body_html": email_html,
            "filename": filename,
            "pdf_base64": pdf_base64
        }

        # 3. Enviar a Power Automate
        url = "https://ce675e3ed2704594af019ed8d7d5f6.d7.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/96148e822d7b4886aaf42c0177ce0678/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=lJ_40qkIBvTGHvo6p4AwB7gOlgCFAl00MYLlAzdV7Z4"
        
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code in [200, 202]:
            return JsonResponse({"status": "success", "message": "Acuerdo enviado correctamente a Power Automate."})
        else:
            return JsonResponse({
                "status": "error", 
                "message": f"Power Automate respondió con error {response.status_code}: {response.text}"
            }, status=400)

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@staff_member_required
@require_POST
def create_ticket_in_cluster_ajax(request, cluster_id):
    """Crea un ticket básico y lo vincula al cluster."""
    import json
    from .models import GrupoTicket, SolicitudTicket
    from django.utils import timezone
    
    try:
        data = json.loads(request.body)
        id_solicitud = data.get('id_solicitud')
        solicitante = data.get('solicitante', 'Manual')
        descripcion = data.get('descripcion', 'Sin descripción')
        
        if not id_solicitud:
            return JsonResponse({'success': False, 'error': 'ID de Solicitud es requerido'})
            
        cluster = get_object_or_404(GrupoTicket, id=cluster_id)
        
        # Crear el ticket
        ticket, created = SolicitudTicket.objects.get_or_create(
            id_solicitud=id_solicitud,
            defaults={
                'solicitante': solicitante,
                'solicitud_descripcion': descripcion,
                'fecha_solicitud': timezone.now()
            }
        )
        
        # Vincular al cluster
        cluster.tickets.add(ticket)
        
        return JsonResponse({
            'success': True, 
            'folio': ticket.folio or ticket.id_solicitud,
            'message': 'Ticket creado y vinculado correctamente' if created else 'Ticket existente vinculado correctamente'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@staff_member_required
def search_tickets_autocomplete_ajax(request):
    """Búsqueda rápida de tickets para autocompletado."""
    from .models import SolicitudTicket
    from django.db.models import Q
    
    q = request.GET.get('q', '')
    if len(q) < 2:
        return JsonResponse({'results': []})
        
    tickets = SolicitudTicket.objects.filter(
        Q(folio__icontains=q) | Q(id_solicitud__icontains=q) | Q(solicitud_descripcion__icontains=q)
    )[:10]
    
    results = []
    for t in tickets:
        # Formatear fecha
        fecha_str = t.fecha_solicitud.strftime('%d/%m/%Y %H:%M') if t.fecha_solicitud else "Sin fecha"
        
        # Obtener ubicación
        ubicacion_str = t.ubicacion.ruta_completa if t.ubicacion else (t.area or "No especificada")
        
        # Descripción completa
        desc_completa = t.solicitud_descripcion or t.falla_descripcion or "Sin descripción"
        
        results.append({
            'id': t.id,
            'id_solicitud': t.id_solicitud,
            'folio': t.folio,
            'text': f"{t.folio or t.id_solicitud} - {desc_completa[:50]}...",
            # Datos adicionales para el card
            'full_description': desc_completa,
            'fecha': fecha_str,
            'ubicacion': ubicacion_str,
            'reportado_por': t.solicitante or "No identificado"
        })
        
    return JsonResponse({'results': results})


@csrf_exempt
def webhook_correo_cierre_callback(request):
    """
    Power Automate llama a este endpoint para confirmar que envió el correo de cierre.
    Espera un POST con JSON: {"folio": "SS26-XXXXXX"}
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        folio = data.get('folio', '').strip()
        
        if not folio:
            return JsonResponse({'error': 'Folio is required'}, status=400)
        
        ticket = SolicitudTicket.objects.filter(folio=folio).first()
        if not ticket:
            # Intentar por id_solicitud
            try:
                ticket = SolicitudTicket.objects.filter(id_solicitud=int(folio)).first()
            except (ValueError, TypeError):
                pass
        
        if not ticket:
            return JsonResponse({'error': 'Ticket not found'}, status=404)
        
        ticket.correo_cierre = True
        ticket.save(update_fields=['correo_cierre'])
        logger.info(f"Correo de cierre confirmado para ticket {ticket.folio}")
        
        return JsonResponse({'success': True, 'folio': ticket.folio})
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error en webhook_correo_cierre_callback: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@staff_member_required
def get_enlace_details_ajax(request, enlace_id):
    """Retorna los datos de Institución y Ubicación de un enlace."""
    from .models import Enlace
    enlace = get_object_or_404(Enlace, id=enlace_id)
    return JsonResponse({
        'institucion_id': enlace.institucion_id,
        'ubicacion_id': enlace.ubicacion_id,
    })

@staff_member_required
def api_busqueda_enlaces_ajax(request):
    """Búsqueda dinámica de Enlaces (Contactos) por nombre o institución."""
    from .models import Enlace
    from django.db.models import Q
    
    q = request.GET.get('q', '')
    if len(q) < 2:
        return JsonResponse({'results': []})
        
    enlaces = Enlace.objects.select_related('institucion', 'ubicacion').filter(
        Q(nombre__icontains=q) | Q(institucion__nombre__icontains=q) | Q(institucion__acronimo__icontains=q)
    )[:15]
    
    results = []
    for e in enlaces:
        results.append({
            'id': e.id,
            'text': f"{e.nombre} - {e.institucion.nombre}",
            'institucion_id': e.institucion_id,
            'inst_nombre': e.institucion.nombre,
            'ubicacion_id': e.ubicacion_id,
            'telefono': e.telefono or "No registrado",
            'email': e.email or "No registrado",
            'ubicacion_nombre': e.ubicacion.nombre if e.ubicacion else "Misma de institución"
        })
        
    return JsonResponse({'results': results})

@staff_member_required
def tiempo_acordado_dashboard_view(request):
    """
    Dashboard para visualizar los Tiempos Acordados y su Timeline.
    Filtrado por departamento del usuario.
    """
    from .models import TiempoAcordado
    from core.models import PerfilUsuario
    
    # 1. Obtener departamento del usuario para filtrado
    user_dept = None
    try:
        if hasattr(request.user, 'perfil'):
            user_dept = request.user.perfil.departamento
    except Exception as e:
        logger.warning(f"Error detectando departamento del usuario: {e}")

    # 2. Queryset Base con optimización
    qs = TiempoAcordado.objects.select_related(
        'ticket', 'enlace', 'institucion', 'ubicacion', 'departamento', 'usuario_creador'
    ).prefetch_related('tareas').order_by('fecha_solucion_final')

    # 3. Lógica de visibilidad por departamento
    if not request.user.is_superuser:
        if user_dept:
            qs = qs.filter(departamento=user_dept)
        else:
            # Respaldo: si no hay departamento, solo ve los creados por él
            qs = qs.filter(usuario_creador=request.user)

    # 4. Estadísticas rápidas
    stats = {
        'total': qs.count(),
        'pendientes': qs.filter(estatus__in=['BORRADOR', 'PENDIENTE']).count(),
        'en_proceso': qs.filter(estatus='APROBADO').count(),
        'vencidos': qs.filter(estatus='VENCIDO').count(),
    }

    context = {
        'acuerdos': qs,
        'stats': stats,
        'user_dept': user_dept,
        'title': 'Dashboard Tiempos Acordados'
    }
    return render(request, 'callcenter/tiempo_acordado/dashboard.html', context)
    
@staff_member_required
def mobile_crear_tiempo_acordado_view(request):
    """Vista Fiori para crear un Tiempo Acordado desde la App."""
    from .models import SolicitudTicket, Enlace, Institucion, TiempoAcordado, TiempoAcordadoTarea
    from activos.models import Ubicacion
    from django.utils import timezone
    from datetime import datetime
    
    if request.method == 'POST':
        try:
            # 1. Crear el Acuerdo Base
            ticket_id = request.POST.get('ticket')
            enlace_id = request.POST.get('enlace')
            ubicacion_id = request.POST.get('ubicacion')
            fecha_final_str = request.POST.get('fecha_solucion_final')
            
            if not ticket_id or not enlace_id or not fecha_final_str:
                return JsonResponse({'success': False, 'error': 'Ticket, Enlace y Fecha Final son requeridos.'})

            acuerdo = TiempoAcordado.objects.create(
                ticket_id=ticket_id,
                enlace_id=enlace_id,
                ubicacion_id=ubicacion_id if ubicacion_id else None,
                motivo_extension=request.POST.get('motivo_extension', ''),
                solucion_provisional=request.POST.get('solucion_provisional', ''),
                observaciones=request.POST.get('observaciones', ''),
                fecha_solucion_final=timezone.make_aware(datetime.fromisoformat(fecha_final_str)),
                usuario_creador=request.user,
                estatus='BORRADOR',
                firma_enlace=request.POST.get('firma_enlace'),
                firma_responsable=request.POST.get('firma_responsable')
            )
            
            # 2. Procesar Tareas del Cronograma
            tareas_desc = request.POST.getlist('tarea_descripcion[]')
            tareas_inicio = request.POST.getlist('tarea_inicio[]')
            tareas_fin = request.POST.getlist('tarea_fin[]')
            
            objs_tareas = []
            for i in range(len(tareas_desc)):
                if tareas_desc[i].strip() and tareas_inicio[i] and tareas_fin[i]:
                    objs_tareas.append(TiempoAcordadoTarea(
                        tiempo_acordado=acuerdo,
                        descripcion=tareas_desc[i],
                        fecha_inicio=timezone.make_aware(datetime.fromisoformat(tareas_inicio[i])),
                        fecha_fin=timezone.make_aware(datetime.fromisoformat(tareas_fin[i]))
                    ))
            
            if objs_tareas:
                TiempoAcordadoTarea.objects.bulk_create(objs_tareas)
                
            return JsonResponse({'success': True, 'id': acuerdo.id})
        except Exception as e:
            logger.error(f"Error creando Tiempo Acordado móvil: {e}", exc_info=True)
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    # Contexto para el GET
    # Solo mostramos ubicaciones que son de tipo EDIFICIO para el primer selector
    edificios = Ubicacion.objects.filter(tipo='EDIFICIO').order_by('nombre')
    enlaces = Enlace.objects.select_related('institucion', 'ubicacion').all().order_by('nombre')
    
    return render(request, 'callcenter/mobile_crear_tiempo_acordado.html', {
        'enlaces': enlaces,
        'edificios': edificios,
        'title': 'Nuevo Tiempo Acordado'
    })

@staff_member_required
def api_get_sububicaciones_ajax(request, parent_id):
    """Retorna sub-ubicaciones (ej. Niveles de un Edificio) para el selector jerárquico."""
    from activos.models import Ubicacion
    sub_ubicaciones = Ubicacion.objects.filter(padre_id=parent_id).order_by('nombre')
    results = []
    for sub in sub_ubicaciones:
        results.append({
            'id': sub.id,
            'nombre': sub.nombre,
            'tipo': sub.get_tipo_display() if hasattr(sub, 'get_tipo_display') else sub.tipo,
        })
    return JsonResponse({'results': results})

@staff_member_required
def cronograma_predefinido_edit_view(request, pk=None):
    """
    Vista unificada para crear o editar un Cronograma Predefinido y sus tareas.
    """
    from .models import CronogramaPredefinido
    from .forms import CronogramaPredefinidoForm, CronogramaItemFormSet
    from django.shortcuts import get_object_or_404, render, redirect
    from django.contrib import messages

    instance = get_object_or_404(CronogramaPredefinido, pk=pk) if pk else None
    
    if request.method == 'POST':
        form = CronogramaPredefinidoForm(request.POST, instance=instance)
        formset = CronogramaItemFormSet(request.POST, instance=instance)
        
        if form.is_valid() and formset.is_valid():
            cronograma = form.save()
            formset.instance = cronograma
            items_guardados = formset.save()
            
            # Segunda pasada: Mapear predecesores por número de tarea
            # Solo si hubo cambios o se crearon items
            todos_los_items = cronograma.items.all()
            dict_items = {str(item.numero): item for item in todos_los_items}
            
            for f in formset.forms:
                if f.instance in todos_los_items and not f.cleaned_data.get('DELETE'):
                    pred_str = f.cleaned_data.get('predecesores_texto', '')
                    if pred_str:
                        num_list = [n.strip() for n in pred_str.replace(';', ',').split(',') if n.strip()]
                        # Limpiar predecesores previos y asignar nuevos
                        preds_to_add = []
                        for n in num_list:
                            if n in dict_items and dict_items[n] != f.instance:
                                preds_to_add.append(dict_items[n])
                        f.instance.predecesores.set(preds_to_add)
                    else:
                        f.instance.predecesores.clear()

            messages.success(request, f"Cronograma '{cronograma.nombre}' guardado exitosamente.")
            return redirect('callcenter:callcenter_cronogramas_lista')
        else:
            messages.error(request, "Error de validación. Por favor revisa los campos.")
    else:
        form = CronogramaPredefinidoForm(instance=instance)
        formset = CronogramaItemFormSet(instance=instance)
        
    context = {
        'form': form,
        'formset': formset,
        'instance': instance,
        'title': "Editar Cronograma" if instance else "Nuevo Cronograma"
    }
    return render(request, 'callcenter/cronograma_predefinido_form.html', context)

@staff_member_required
def cronograma_predefinido_lista_view(request):
    """Lista simple de cronogramas predefinidos."""
    from .models import CronogramaPredefinido
    from django.shortcuts import render
    cronogramas = CronogramaPredefinido.objects.all().select_related('departamento')
    return render(request, 'callcenter/cronograma_predefinido_lista.html', {'cronogramas': cronogramas})
