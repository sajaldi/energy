from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .tasks import sync_tickets_task, sync_tickets_automatico_task
from django.contrib.admin.views.decorators import staff_member_required
from core.decorators import mobile_permission_required
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
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.utils import timezone
from playwright.sync_api import sync_playwright
from .models import SolicitudTicket, EvidenciaTicket, CronogramaPredefinido, CronogramaItemPredefinido, RestriccionAcceso, GrupoTicket, FallaTicket, HistorialTicket
from .utils import resolve_ticket_ubicacion
import requests
from core.models import PerfilUsuario, Departamento
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


def add_historial(ticket, accion, usuario=None, descripcion=''):
    HistorialTicket.objects.create(
        ticket=ticket,
        accion=accion,
        usuario=usuario,
        descripcion=descripcion
    )


@staff_member_required
def trigger_sync_tickets(request):
    days = int(request.GET.get('days', 2))
    fecha_inicio = request.GET.get('fecha_inicio', '').strip() or None
    fecha_fin = request.GET.get('fecha_fin', '').strip() or None
    try:
        sync_tickets_task.delay(days=days, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
        if fecha_inicio and fecha_fin:
            messages.success(request, f"Se ha iniciado la sincronización del {fecha_inicio} al {fecha_fin} en segundo plano.")
        else:
            messages.success(request, f"Se ha iniciado la sincronización de los últimos {days} días en segundo plano.")
    except Exception as e:
        logger.error(f"Error al iniciar la sincronización: {e}")
        messages.error(request, f"Error al iniciar la sincronización: {e}")
    return redirect('admin:callcenter_solicitudticket_changelist')

@staff_member_required
def trigger_bulk_analysis_n8n(request):
    """
    Inicia la vectorización masiva de todos los tickets pendientes en n8n.
    """
    from .tasks import bulk_vectorize_n8n
    try:
        bulk_vectorize_n8n.delay(only_missing=True)
        messages.success(request, "Se ha iniciado el análisis masivo (n8n) de los tickets pendientes en segundo plano.")
    except Exception as e:
        logger.error(f"Error al iniciar el análisis masivo: {e}")
        messages.error(request, f"Error al iniciar el análisis masivo: {e}")
    return redirect('admin:callcenter_solicitudticket_changelist')
    
@staff_member_required
def trigger_sync_tickets_automatico(request):
    try:
        sync_tickets_automatico_task.delay()
        messages.success(request, "Robot de sincronización automática iniciado en segundo plano (sin filtro de fechas).")
    except Exception as e:
        logger.error(f"Error al iniciar sincronización automática: {e}")
        messages.error(request, f"Error al iniciar sincronización automática: {e}")
    return redirect('admin:callcenter_solicitudticket_changelist')


@staff_member_required
def trigger_sync_by_folios(request):
    """
    Inicia la sincronización de tickets específicos por folio.
    Recibe un parámetro 'folios' (string separado por comas).
    """
    from .tasks import sync_tickets_by_folio_list_task
    folios_str = request.GET.get('folios', '').strip()
    if not folios_str:
        messages.error(request, "No se proporcionaron folios para sincronizar.")
        return redirect('admin:callcenter_solicitudticket_changelist')
        
    # Limpiar y separar folios
    folios_list = [f.strip() for f in folios_str.replace(',', ' ').split() if f.strip()]
    
    if not folios_list:
        messages.error(request, "La lista de folios es inválida.")
        return redirect('admin:callcenter_solicitudticket_changelist')
        
    try:
        sync_tickets_by_folio_list_task.delay(folios_list)
        messages.success(request, f"Se ha iniciado la sincronización de {len(folios_list)} tickets específicos en segundo plano.")
    except Exception as e:
        logger.error(f"Error al iniciar la sincronización por folios: {e}")
        messages.error(request, f"Error al iniciar la sincronización: {e}")
        
    return redirect('admin:callcenter_solicitudticket_changelist')


def send_ticket_to_power_automate_view(request, ticket_id):
    # Limpiar ID de posibles comas de formateo regional
    ticket_id = int(str(ticket_id).replace(',', ''))
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
            # Disparar sync SIG solo después de notificación exitosa
            from .tasks import sync_single_ticket_task
            sync_single_ticket_task.delay(ticket.id)
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
    Buscador Híbrido de tickets:
    1. Semántico: Usa embeddings vectoriales (Ollama + PGVector).
    2. Palabra Clave: Búsqueda tradicional icontains en campos clave.
    Combina ambos resultados para mayor robustez.
    """
    from django.shortcuts import render
    from django.conf import settings
    from django.db.models import Q
    import requests as http_requests
    
    query = request.GET.get('q', '').strip()
    resultados_finales = []
    error = None
    
    if query:
        # --- 1. BÚSQUEDA TRADICIONAL (Palabra Clave) ---
        # Útil para tickets sin embedding o búsquedas exactas
        keyword_q = Q(folio__icontains=query) | \
                    Q(solicitud_descripcion__icontains=query) | \
                    Q(falla_descripcion__icontains=query) | \
                    Q(area__icontains=query) | \
                    Q(nivel__icontains=query) | \
                    Q(servicio__icontains=query)
        
        if query.isdigit():
            keyword_q |= Q(id_solicitud=query)
            
        keyword_results = SolicitudTicket.objects.filter(keyword_q).select_related('ubicacion')[:50]
        for t in keyword_results:
            t.similitud = 70.0  # Puntaje base para coincidencia por palabra clave
            t.metodo = "Palabra Clave"
        
        # --- 2. BÚSQUEDA SEMÁNTICA ---
        semantic_results = []
        try:
            ollama_url = f'{settings.OLLAMA_API_URL}/api/embeddings'
            resp = http_requests.post(ollama_url, json={
                'model': 'mxbai-embed-large',
                'prompt': f"Represent this query for retrieving relevant documents: {query}"
            }, timeout=15) # Timeout más corto para no bloquear
            
            if resp.status_code == 200:
                query_embedding = resp.json().get('embedding')
                if query_embedding:
                    # Buscamos sin filtros estrictos para que la semántica trabaje el contexto
                    semantic_results = SolicitudTicket.buscar_vectorial(query_embedding, limit=50)
                    for t in semantic_results:
                        t.similitud = round(max(0, min(100, (1 - t.distancia) * 100)), 1)
                        t.metodo = "IA Semántica"
            else:
                logger.warning(f"Ollama falló: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Error en búsqueda semántica (posiblemente Ollama offline): {e}")
            # No bloqueamos el error para permitir que los resultados por palabra clave se vean

        # --- 3. COMBINACIÓN Y RANKING ---
        # Usamos un diccionario para evitar duplicados, priorizando el puntaje más alto
        seen_ids = {}
        
        # Prioridad a los semánticos si son buenos matches (>75%)
        for t in semantic_results:
            seen_ids[t.id] = t
            
        # Añadir keyword results
        for t in keyword_results:
            if t.id in seen_ids:
                # Si ya estaba, le damos un boost si también coincide por palabra clave
                seen_ids[t.id].similitud = min(100, seen_ids[t.id].similitud + 5)
            else:
                seen_ids[t.id] = t
        
        # Ordenar por similitud
        resultados_finales = sorted(seen_ids.values(), key=lambda x: x.similitud, reverse=True)
    
    return render(request, 'callcenter/buscar_tickets.html', {
        'query': query,
        'resultados': resultados_finales,
        'error': error,
    })


@staff_member_required
def ticket_cierre_visual_view(request, ticket_id):
    # Limpiar ID de posibles comas de formateo regional
    ticket_id = int(str(ticket_id).replace(',', ''))
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
    
    if request.method == 'POST':
        # AJAX Save Progress
        fecha_cierre_str = request.POST.get('fecha_cierre')
        if fecha_cierre_str:
            from django.utils import timezone
            from datetime import datetime
            dt = None
            # Intentar varios formatos comunes
            for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
                try:
                    dt = datetime.strptime(fecha_cierre_str, fmt)
                    ticket.fecha_cierre = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                    break
                except ValueError:
                    # Fallback si el formato falla
                    pass
            else:
                # Si falla todo, dejar que Django intente procesar el string o mantener el actual
                pass
        
        ticket.diagnostico = request.POST.get('diagnostico', '')
        ticket.actividades = request.POST.get('actividades', '')
        ticket.observaciones = request.POST.get('observaciones', '')
        
        # Diagnóstico del Catálogo
        diagnostico_reportado_id = request.POST.get('diagnostico_reportado')
        if diagnostico_reportado_id:
            ticket.diagnostico_reportado_id = int(diagnostico_reportado_id)
        else:
            ticket.diagnostico_reportado = None

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

        ticket.solicitud_adicional = request.POST.get('solicitud_adicional') == 'on'
            
        ticket.save()
        add_historial(ticket, 'CIERRE_VISUAL', usuario=request.user, descripcion="Cierre visual realizado")
        return JsonResponse({'success': True})

    evidences = EvidenciaTicket.objects.filter(ticket=ticket).order_by('-id')
    from mantenimiento.models import Empresa
    proveedores = Empresa.objects.filter(activo=True).order_by('nombre')
    
    diagnosticos_disponibles = []
    if ticket.falla_reportada:
        diagnosticos_disponibles = ticket.falla_reportada.get_all_diagnosticos()

    return render(request, 'callcenter/ticket_cierre_visual.html', {
        'ticket': ticket,
        'evidences': evidences,
        'evidences_count': evidences.count(),
        'proveedores': proveedores,
        'diagnosticos_disponibles': diagnosticos_disponibles,
        'opts': SolicitudTicket._meta,
    })

@csrf_exempt
@staff_member_required
def upload_evidencia_ajax(request, ticket_id):
    # Limpiar ID de posibles comas de formateo regional
    ticket_id = int(str(ticket_id).replace(',', ''))
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
    if request.method == 'POST' and request.FILES:
        files = request.FILES.getlist('files')
        for f in files:
            evidencia = EvidenciaTicket.objects.create(
                ticket=ticket, 
                descripcion=f"Foto Evidencia {datetime.now().strftime('%H:%M')}",
                analizada=False
            )
            # Extraer extensión y generar nombre único
            ext = f.name.split('.')[-1] if '.' in f.name else 'jpg'
            file_name = f'evidencia_{ticket.id}_{uuid.uuid4().hex[:6]}.{ext}'
            evidencia.archivo.save(file_name, f)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@csrf_exempt
@staff_member_required
def analyze_evidence_ai_ajax(request, evidencia_id):
    if request.method == 'POST':
        from .tasks import analyze_image_ai
        analyze_image_ai.delay(evidencia_id)
        return JsonResponse({'success': True, 'message': 'Análisis iniciado en segundo plano.'})
    return JsonResponse({'success': False}, status=400)

@csrf_exempt
@staff_member_required
def delete_evidencia_ajax(request, ticket_id, evidencia_id):
    # Limpiar ID de posibles comas de formateo regional
    ticket_id = int(str(ticket_id).replace(',', ''))
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

def get_filtered_ticket_qs(request):
    """Helper para obtener el queryset de tickets filtrado por fecha."""
    from datetime import datetime, timedelta
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    
    qs = SolicitudTicket.objects.all()
    
    if fecha_inicio_str:
        try:
            f_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
            qs = qs.filter(fecha_solicitud__gte=f_inicio)
        except ValueError: pass
    else:
        # Default: últimos 30 días
        f_inicio = datetime.now() - timedelta(days=30)
        qs = qs.filter(fecha_solicitud__gte=f_inicio)
        
    if fecha_fin_str:
        try:
            f_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            qs = qs.filter(fecha_solicitud__lte=f_fin)
        except ValueError: pass
    return qs

@staff_member_required
def ticket_dashboard_view(request):
    """
    Dashboard principal de tickets y grupos (clusters).
    """
    from django.db.models import Count, Q
    from datetime import datetime
    
    from core.models import Departamento
    from activos.models.ubicacion import Ubicacion
    from activos.models.categoria import Categoria
    from callcenter.models import SolicitudTicket, GrupoTicket, FallaTicket
    from django.core.cache import cache

    # --- Filtros de Fecha ---
    ticket_qs = get_filtered_ticket_qs(request)
    
    # Re-obtener strings para el context si es necesario (o usar lo que vino en GET)
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')

    # Métricas Globales (Filtradas en una sola query)
    metrics = ticket_qs.aggregate(
        total=Count('id'),
        cerrados=Count('id', filter=Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True))
    )
    total_tickets = metrics['total'] or 0
    tickets_cerrados = metrics['cerrados'] or 0
    tickets_abiertos = total_tickets - tickets_cerrados
    
    # --- CACHE PARA DATOS PESADOS (Clusters y Árbol) ---
    cache_key = f"ticket_dashboard_heavy_{request.user.id}_{fecha_inicio_str}_{fecha_fin_str}"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        grupos_por_depto = cached_data['grupos_por_depto']
        flat_nodes = cached_data['flat_nodes']
        cat_labels = cached_data.get('cat_labels', [])
        cat_data = cached_data.get('cat_data', [])
        falla_diagnosticos_json_map = cached_data.get('falla_diagnosticos_json_map', {})
    else:
        # 2. Cargar Catálogos (Necesarios para clusters y árbol)
        deptos = {d.id: d for d in Departamento.objects.all()}
        fallas = {f.id: f for f in FallaTicket.objects.all()}
        ubicaciones = {u.id: u for u in Ubicacion.objects.all()}

        # Grupos Recientes
        raw_grupos_qs = GrupoTicket.objects.annotate(
            num_tickets=Count('tickets'),
            num_cerrados=Count('tickets', filter=Q(tickets__fecha_cierre__isnull=False) | Q(tickets__cierre_enviado=True)),
            num_abiertos=Count('tickets', filter=Q(tickets__fecha_cierre__isnull=True) & Q(tickets__cierre_enviado=False))
        ).select_related('usuario_creador', 'departamento', 'usuario_creador__perfil')

        # Seguridad: Filtrar por departamento
        perfil = getattr(request.user, 'perfil', None)
        user_depto_id = perfil.departamento_id if perfil else None
        
        if not request.user.is_superuser and user_depto_id:
            raw_grupos_qs = raw_grupos_qs.filter(
                Q(departamento_id=user_depto_id) | 
                Q(usuario_creador__perfil__departamento_id=user_depto_id)
            )
        elif not request.user.is_superuser and not user_depto_id:
            raw_grupos_qs = raw_grupos_qs.none()

        raw_grupos = raw_grupos_qs.order_by('-fecha')[:20]

        # Agrupar grupos por departamento
        grupos_por_depto = {}
        for g in raw_grupos:
            did = g.departamento_id
            if not did and g.usuario_creador:
                pc = getattr(g.usuario_creador, 'perfil', None)
                did = pc.departamento_id if pc else None
            
            if not did:
                main_depto_info = g.tickets.values('falla_reportada__departamento_responsable_id').annotate(
                    count=Count('id')
                ).order_by('-count').first()
                did = main_depto_info['falla_reportada__departamento_responsable_id'] if main_depto_info else 0
            
            if not did: did = 0
            depto_obj = deptos.get(did)
            depto_name = depto_obj.nombre if depto_obj else "Sin Departamento"
            if depto_name not in grupos_por_depto:
                grupos_por_depto[depto_name] = []
            grupos_por_depto[depto_name].append(g)

        # --- AGREGACIÓN MULTIDIMENSIONAL ---
        raw_stats = ticket_qs.values(
            'falla_reportada__departamento_responsable_id',
            'falla_reportada_id', 
            'ubicacion_id'
        ).annotate(
            t_total=Count('id'),
            t_abiertos=Count('id', filter=Q(fecha_cierre__isnull=True) & Q(cierre_enviado=False)),
            t_cerrados=Count('id', filter=Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True))
        )

        d_data = {}
        for stat in raw_stats:
            did = stat['falla_reportada__departamento_responsable_id'] or 0
            fid = stat['falla_reportada_id']
            uid = stat['ubicacion_id']
            if not fid: continue
            if did not in d_data: d_data[did] = {}
            if fid not in d_data[did]: d_data[did][fid] = {'total': 0, 'abiertos': 0, 'cerrados': 0, 'locs': {}}
            d_data[did][fid]['total'] += stat['t_total']
            d_data[did][fid]['abiertos'] += stat['t_abiertos']
            d_data[did][fid]['cerrados'] += stat['t_cerrados']
            if uid:
                if uid not in d_data[did][fid]['locs']: d_data[did][fid]['locs'][uid] = {'total': 0, 'abiertos': 0, 'cerrados': 0}
                d_data[did][fid]['locs'][uid]['total'] += stat['t_total']
                d_data[did][fid]['locs'][uid]['abiertos'] += stat['t_abiertos']
                d_data[did][fid]['locs'][uid]['cerrados'] += stat['t_cerrados']

        def build_loc_tree(loc_stats, offset_level, parent_dom_id):
            relevant_uids = set(loc_stats.keys()); all_uids = set()
            for uid in relevant_uids:
                curr = uid
                while curr:
                    all_uids.add(curr); u_obj = ubicaciones.get(curr); curr = u_obj.padre_id if u_obj else None
            u_nodes = {uid: {'id': uid, 'nombre': ubicaciones[uid].nombre, 'padre_id': ubicaciones[uid].padre_id, 'total': loc_stats.get(uid, {}).get('total', 0), 'abiertos': loc_stats.get(uid, {}).get('abiertos', 0), 'cerrados': loc_stats.get(uid, {}).get('cerrados', 0), 'children': [], 'is_loc': True, 'dom_id': f"{parent_dom_id}-loc-{uid}"} for uid in all_uids if uid in ubicaciones}
            u_roots = []
            for uid, node in u_nodes.items():
                if node['padre_id'] and node['padre_id'] in u_nodes:
                    node['dom_parent_id'] = node['dom_id'].replace(f"-loc-{uid}", f"-loc-{node['padre_id']}")
                    u_nodes[node['padre_id']]['children'].append(node)
                else: node['dom_parent_id'] = parent_dom_id; u_roots.append(node)
            def acc_u(node, level):
                node['level'] = level
                for c in node['children']:
                    cs = acc_u(c, level + 1); node['total'] += cs['total']; node['abiertos'] += cs['abiertos']; node['cerrados'] += cs['cerrados']
                return node
            for r in u_roots: acc_u(r, offset_level)
            return u_roots

        def build_falla_tree(f_stats_dict, offset_level, parent_dom_id):
            relevant_fids = set(f_stats_dict.keys()); all_fids = set()
            for fid in relevant_fids:
                curr = fid
                while curr:
                    all_fids.add(curr); f_obj = fallas.get(curr); curr = f_obj.parent_id if f_obj else None
            f_nodes = {fid: {'id': fid, 'nombre': fallas[fid].nombre, 'padre_id': fallas[fid].parent_id, 'total': f_stats_dict.get(fid, {}).get('total', 0), 'abiertos': f_stats_dict.get(fid, {}).get('abiertos', 0), 'cerrados': f_stats_dict.get(fid, {}).get('cerrados', 0), 'children': [], 'loc_stats': f_stats_dict.get(fid, {}).get('locs', {}), 'is_falla': True, 'dom_id': f"{parent_dom_id}-fail-{fid}"} for fid in all_fids if fid in fallas}
            f_roots = []
            for fid, node in f_nodes.items():
                if node['padre_id'] and node['padre_id'] in f_nodes:
                    node['dom_parent_id'] = node['dom_id'].replace(f"-fail-{fid}", f"-fail-{node['padre_id']}")
                    f_nodes[node['padre_id']]['children'].append(node)
                else: node['dom_parent_id'] = parent_dom_id; f_roots.append(node)
            def acc_f(node, level):
                node['level'] = level
                for c in node['children']:
                    cs = acc_f(c, level + 1); node['total'] += cs['total']; node['abiertos'] += cs['abiertos']; node['cerrados'] += cs['cerrados']
                    for lid, ls in cs['loc_stats'].items():
                        if lid not in node['loc_stats']: node['loc_stats'][lid] = {'total':0,'abiertos':0,'cerrados':0}
                        node['loc_stats'][lid]['total'] += ls['total']; node['loc_stats'][lid]['abiertos'] += ls['abiertos']; node['loc_stats'][lid]['cerrados'] += ls['cerrados']
                node['loc_tree'] = build_loc_tree(node['loc_stats'], node['level'] + 1, node['dom_id'])
                return node
            for r in f_roots: acc_f(r, offset_level)
            return f_roots

        def flatten_tree(nodes, flattened_list):
            for node in nodes:
                flattened_list.append(node)
                if 'children' in node and node['children']: flatten_tree(node['children'], flattened_list)
                if 'loc_tree' in node and node['loc_tree']: flatten_tree(node['loc_tree'], flattened_list)

        temp_tree = []
        for did, f_stats in d_data.items():
            depto_name = deptos[did].nombre if did in deptos else "Sin Departamento"
            depto_dom_id = f"dep-{did}"
            d_node = {
                'id': did, 'nombre': depto_name, 'is_depto': True, 'level': 0, 'total': 0, 'abiertos': 0, 'cerrados': 0,
                'dom_id': depto_dom_id, 'dom_parent_id': 'none',
                'children': build_falla_tree(f_stats, 1, depto_dom_id)
            }
            for fn in d_node['children']:
                d_node['total'] += fn['total']; d_node['abiertos'] += fn['abiertos']; d_node['cerrados'] += fn['cerrados']
            if d_node['total'] > 0: temp_tree.append(d_node)

        temp_tree.sort(key=lambda x: x['total'], reverse=True)
        flat_nodes = []
        flatten_tree(temp_tree, flat_nodes)
        
        # Gráficas - cached junto con el resto
        cat_stats = ticket_qs.filter(ubicacion__categoria__isnull=False).values('ubicacion__categoria__nombre').annotate(
            total=Count('id')
        ).order_by('-total')[:10]
        cat_labels = [c['ubicacion__categoria__nombre'] for c in cat_stats]
        cat_data = [c['total'] for c in cat_stats]

        from callcenter.models import DiagnosticoTicket
        catalog_diags = DiagnosticoTicket.objects.select_related('falla').all()
        
        falla_diagnosticos_map = {}
        for diag in catalog_diags:
            falla_nombre = diag.falla.nombre
            if falla_nombre not in falla_diagnosticos_map:
                falla_diagnosticos_map[falla_nombre] = {}
            falla_diagnosticos_map[falla_nombre][diag.nombre] = 0
            
        diag_stats = ticket_qs.filter(
            falla_reportada__isnull=False,
            diagnostico_reportado__isnull=False
        ).values(
            'falla_reportada__nombre',
            'diagnostico_reportado__nombre'
        ).annotate(
            total=Count('id')
        )
        
        for item in diag_stats:
            falla_nombre = item['falla_reportada__nombre']
            diag_nombre = item['diagnostico_reportado__nombre']
            total = item['total']
            
            if falla_nombre not in falla_diagnosticos_map:
                falla_diagnosticos_map[falla_nombre] = {}
            falla_diagnosticos_map[falla_nombre][diag_nombre] = total
            
        falla_diagnosticos_json_map = {}
        for falla_nombre, diags_dict in falla_diagnosticos_map.items():
            sorted_diags = sorted(diags_dict.items(), key=lambda x: x[1], reverse=True)
            falla_diagnosticos_json_map[falla_nombre] = [
                {'name': name, 'value': value} for name, value in sorted_diags
            ]

        cache.set(cache_key, {
            'grupos_por_depto': grupos_por_depto,
            'flat_nodes': flat_nodes,
            'cat_labels': cat_labels,
            'cat_data': cat_data,
            'falla_diagnosticos_json_map': falla_diagnosticos_json_map,
        }, 300)

    departamentos_qs = Departamento.objects.all().order_by('nombre')

    context = {
        'total': total_tickets,
        'cerrados': tickets_cerrados,
        'abiertos': tickets_abiertos,
        'grupos_por_depto': grupos_por_depto,
        'flat_nodes': flat_nodes,
        'cat_labels_json': json.dumps(cat_labels),
        'cat_data_json': json.dumps(cat_data),
        'falla_diagnosticos_json': json.dumps(falla_diagnosticos_json_map),
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'title': 'Dashboard de Tickets',
        'departamentos': departamentos_qs,
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
    
    from django.db.models import Prefetch, Count, Q, Sum
    from .models import FallaTicket
    from django.contrib.auth.models import User
    
    # Limpiar ID de posibles comas de formateo regional
    cluster_id = int(str(cluster_id).replace(',', ''))
    cluster = get_object_or_404(GrupoTicket.objects.select_related('usuario_creador', 'departamento'), id=cluster_id)
    
    # SEGURIDAD: Restricción por Departamento
    if not request.user.is_superuser:
        user_depto_id = getattr(request.user.perfil, 'departamento_id', None) if hasattr(request.user, 'perfil') else None
        
        if not user_depto_id:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Tu usuario no tiene un departamento asignado. Contacta al administrador.")

        # Obtener deptos vinculados al cluster
        cluster_depto_id = cluster.departamento_id
        creator_depto_id = None
        if cluster.usuario_creador and hasattr(cluster.usuario_creador, 'perfil'):
            creator_depto_id = cluster.usuario_creador.perfil.departamento_id
            
        # Si no coincide con ninguno, denegar acceso
        if user_depto_id not in [cluster_depto_id, creator_depto_id]:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("No tienes permiso para acceder a este cluster (Restricción de Departamento).")
    
    # Parámetros de Filtro y Búsqueda
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status')
    falla_id = request.GET.get('falla')
    sort = request.GET.get('sort')
    
    # Optimizamos agregando relaciones necesarias
    tickets = cluster.tickets.all().select_related(
        'ubicacion', 'usuario_responsable', 'restriccion_acceso', 'falla_reportada', 'falla_reportada__parent', 'diagnostico_reportado'
    ).annotate(
        num_tiempos_acordados=Count('tiempos_acordados')
    )

    # Ordenamiento base
    if sort == 'estado':
        tickets = tickets.order_by('fecha_cierre', 'cierre_enviado', '-fecha_solicitud')
    elif sort == '-estado':
        tickets = tickets.order_by('-fecha_cierre', '-cierre_enviado', '-fecha_solicitud')
    else:
        tickets = tickets.order_by('falla_reportada__parent__nombre', 'falla_reportada__nombre', '-fecha_solicitud')
    
    # Aplicar búsqueda por texto (q)
    if q:
        search_q = Q(folio__icontains=q) | Q(solicitud_descripcion__icontains=q) | Q(responsable__icontains=q)
        if q.isdigit():
            search_q |= Q(id_solicitud=q)
        tickets = tickets.filter(search_q | Q(usuario_responsable__first_name__icontains=q) | Q(usuario_responsable__last_name__icontains=q)).distinct()
        
    # Filtro por Status
    if status == 'abiertos':
        tickets = tickets.filter(fecha_cierre__isnull=True, cierre_enviado=False)
    elif status == 'cerrados':
        tickets = tickets.filter(Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True))

    # Filtro por Falla
    if falla_id:
        tickets = tickets.filter(falla_reportada_id=falla_id)

    # Filtro Especial (Interno, Restricción, Tiempo Acordado)
    filtro_especial = request.GET.get('filtro_especial')
    if filtro_especial == 'interno':
        tickets = tickets.filter(es_interno=True)
    elif filtro_especial == 'externo':
        tickets = tickets.filter(es_interno=False)
    elif filtro_especial == 'restriccion':
        tickets = tickets.filter(restriccion_acceso__isnull=False)
    elif filtro_especial == 'tiempo_acordado':
        tickets = tickets.filter(num_tiempos_acordados__gt=0)

    # Filtro por Correo de Cierre
    correo_cierre = request.GET.get('correo_cierre')
    if correo_cierre == 'con':
        tickets = tickets.filter(correo_cierre=True)
    elif correo_cierre == 'sin':
        tickets = tickets.filter(Q(correo_cierre=False) | Q(correo_cierre__isnull=True))

    # Obtener fallas únicas presentes en este cluster para el filtro
    fallas_ids = cluster.tickets.values_list('falla_reportada_id', flat=True).distinct()
    fallas_opciones = FallaTicket.objects.filter(id__in=fallas_ids).order_by('nombre')

    # Calcular estadísticas dirigidas
    total = tickets.count()
    cerrados_count = tickets.filter(Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True)).count()
    abiertos_count = total - cerrados_count
    
    # Calcular deductiva total en el filtro actual
    total_deductiva = tickets.aggregate(total=Sum('deductiva'))['total'] or 0.00
    total_deductiva_abiertos = tickets.exclude(Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True)).aggregate(total=Sum('deductiva'))['total'] or 0.00
    total_deductiva_cerrados = tickets.filter(Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True)).aggregate(total=Sum('deductiva'))['total'] or 0.00
    
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
                'Fecha Finalización': t.fecha_cierre.strftime('%d/%m/%Y %H:%M') if t.fecha_cierre else '',
                'Diagnóstico': t.diagnostico or '',
                'Acciones Realizadas': t.actividades or '',
                'Deductiva (USD)': float(t.deductiva) if t.deductiva else 0.0,
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
            'cerrados': cerrados_count,
            'abiertos': abiertos_count,
            'total_deductiva': total_deductiva,
            'total_deductiva_abiertos': total_deductiva_abiertos,
            'total_deductiva_cerrados': total_deductiva_cerrados,
            'fecha_reporte': timezone.now()
        })
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Reporte_Cluster_{cluster.correlativo}.pdf"'
        pisa_status = pisa.CreatePDF(html_content, dest=response)
        if pisa_status.err:
            return HttpResponse('Error al generar PDF', status=500)
        return response

    # === Lógica para las Gráficas (Chart.js) - Exportación Plana para PowerBI-like filter ===
    import json
    raw_tickets = []
    
    for t in tickets:
        # Falla
        f_name = t.falla_reportada.nombre if t.falla_reportada else 'Sin Clasificar'
        
        # Falla Padre
        fp_name = t.falla_reportada.parent.nombre if (t.falla_reportada and t.falla_reportada.parent) else (t.falla_reportada.nombre if t.falla_reportada else 'Sin Clasificar')
        
        # Ubicación (Lista jerárquica)
        ruta = t.ubicacion_jerarquica if hasattr(t, 'ubicacion_jerarquica') else (t.ubicacion.ruta_completa if t.ubicacion else (t.nivel or 'Otra'))
        
        # Soportar separadores: ' → ' (unicode), ' > ', ' -> '
        ruta_str = str(ruta) if ruta else 'Otra'
        if ' → ' in ruta_str:
            sep = ' → '
        elif ' -> ' in ruta_str:
            sep = ' -> '
        elif ' > ' in ruta_str:
            sep = ' > '
        else:
            sep = None
        partes = [p.strip() for p in ruta_str.split(sep)] if sep else [ruta_str]
        
        # Tiempos
        duracion_horas = None
        if t.fecha_cierre and t.fecha_solicitud:
            dh = (t.fecha_cierre - t.fecha_solicitud).total_seconds() / 3600.0
            if dh >= 0:
                duracion_horas = dh
                
        raw_tickets.append({
            'id': str(t.id),
            'f': f_name,
            'fp': fp_name,
            'u': partes,
            'd': duracion_horas,
            'c': bool(t.fecha_cierre or t.cierre_enviado),
            'deductiva': float(t.deductiva) if t.deductiva else 0.0,
            'diag': t.diagnostico_reportado.nombre if t.diagnostico_reportado else None
        })

    # Catálogo de diagnósticos por tipo de falla
    from callcenter.models import DiagnosticoTicket
    catalog_diags = DiagnosticoTicket.objects.select_related('falla').all()
    falla_diagnosticos_catalog = {}
    for diag in catalog_diags:
        fname = diag.falla.nombre
        if fname not in falla_diagnosticos_catalog:
            falla_diagnosticos_catalog[fname] = []
        falla_diagnosticos_catalog[fname].append(diag.nombre)

    chart_data = {
        'raw_tickets': raw_tickets,
        'diagnosticos_catalog': falla_diagnosticos_catalog
    }

    context = {
        'cluster': cluster,
        'tickets': tickets,
        'fallas_opciones': fallas_opciones,
        'total': total,
        'cerrados': cerrados_count,
        'abiertos': abiertos_count,
        'total_deductiva': total_deductiva,
        'total_deductiva_abiertos': total_deductiva_abiertos,
        'total_deductiva_cerrados': total_deductiva_cerrados,
        'q': q,
        'title': f'Tickets en {cluster.correlativo}',
        'chart_data_json': json.dumps(chart_data)
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
    # Limpiar ID de posibles comas de formateo regional
    ticket_id = int(str(ticket_id).replace(',', ''))
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
    # Limpiar ID de posibles comas de formateo regional
    ticket_id = int(str(ticket_id).replace(',', ''))
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
    # Limpiar ID de posibles comas de formateo regional
    ticket_id = int(str(ticket_id).replace(',', ''))
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
def wizard_cluster_view(request):
    """
    Wizard para agrupar tickets masivamente (Clusterización).
    1. Filtra por Departamento y Rango de Fechas.
    2. Asigna responsables del catálogo a tickets vacíos.
    3. Crea o Actualiza un GrupoTicket (Cluster).
    """
    from core.models import Departamento
    from django.utils import timezone
    from datetime import datetime
    from django.db.models import Q

    departamentos = Departamento.objects.all().order_by('nombre')
    now_str = timezone.now().strftime('%Y-%m-%d')
    
    # Soporte para actualización de clusters existentes
    cluster_id = request.GET.get('cluster_id') or request.POST.get('cluster_id')
    existing_cluster = None
    if cluster_id:
        existing_cluster = get_object_or_404(GrupoTicket, id=cluster_id)

    if request.method == 'POST':
        action = request.POST.get('action') # 'preview' o 'execute'
        depto_id = request.POST.get('departamento')
        fecha_inicio_str = request.POST.get('fecha_inicio')
        fecha_fin_str = request.POST.get('fecha_fin')
        
        if not depto_id or not fecha_inicio_str or not fecha_fin_str:
            messages.error(request, "Todos los campos son obligatorios.")
            return render(request, 'callcenter/wizard_cluster.html', {
                'departamentos': departamentos,
                'now': now_str,
                'existing_cluster': existing_cluster
            })

        # Parsear fechas
        fecha_inicio = timezone.make_aware(datetime.strptime(fecha_inicio_str, '%Y-%m-%d'))
        fecha_fin = timezone.make_aware(datetime.combine(datetime.strptime(fecha_fin_str, '%Y-%m-%d'), datetime.max.time()))
        
        depto = get_object_or_404(Departamento, id=depto_id)
        
        # Procesar folios manuales
        manual_folios_raw = request.POST.get('manual_folios', '')
        import re
        manual_folios = re.split(r'[\s,]+', manual_folios_raw)
        manual_folios = [f.strip() for f in manual_folios if f.strip()]

        # 1. Buscar Fallas del Catálogo vinculadas al departamento
        fallas_ids = FallaTicket.objects.filter(departamento_responsable=depto).values_list('id', flat=True)
        
        # 2. Construir Filtro
        # Por defecto: Por departamento y rango de fechas
        q_filter = Q(falla_reportada_id__in=fallas_ids, fecha_solicitud__range=(fecha_inicio, fecha_fin))
        
        # Opcional: Agregar folios pegados manualmente
        if manual_folios:
            # Separar folios numéricos para id_solicitud (BigIntegerField) para evitar ValueError
            numeric_folios = [f for f in manual_folios if f.isdigit()]
            q_filter_manual = Q(folio__in=manual_folios)
            if numeric_folios:
                q_filter_manual |= Q(id_solicitud__in=numeric_folios)
            
            q_filter |= q_filter_manual

        tickets_qs = SolicitudTicket.objects.filter(q_filter).select_related(
            'falla_reportada', 'falla_reportada__usuario_responsable', 'ubicacion', 'usuario_responsable'
        ).distinct()
        
        if action == 'preview':
            return render(request, 'callcenter/wizard_cluster.html', {
                'departamentos': departamentos,
                'selected_depto': depto,
                'fecha_inicio': fecha_inicio_str,
                'fecha_fin': fecha_fin_str,
                'tickets_count': tickets_qs.count(),
                'tickets_preview': tickets_qs[:50], 
                'preview_mode': True,
                'manual_folios_raw': manual_folios_raw,
                'title': 'Previsualización del Cluster',
                'now': now_str,
                'existing_cluster': existing_cluster
            })
            
        elif action == 'execute':
            if existing_cluster:
                cluster = existing_cluster
                # Actualizar departamento si no lo tenía
                if not cluster.departamento:
                    cluster.departamento = depto
                    cluster.save(update_fields=['departamento'])
                msg_prefix = f"¡Éxito! Se ha actualizado el cluster '{cluster.correlativo}'."
            else:
                # Nomenclatura Automática: [Departamento] - [Fecha Inicio] a [Fecha Fin]
                correlativo = f"{depto.nombre} - {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}"
                
                # Asegurar unicidad del correlativo
                base_correlativo = correlativo
                counter = 1
                while GrupoTicket.objects.filter(correlativo=correlativo).exists():
                    correlativo = f"{base_correlativo} ({counter})"
                    counter += 1
                    
                cluster = GrupoTicket.objects.create(
                    correlativo=correlativo,
                    departamento=depto,
                    descripcion=f"Cluster generado automáticamente por Wizard para {depto.nombre}"
                )
                msg_prefix = f"¡Éxito! Se ha creado el cluster '{correlativo}'."
            
            count_assigned = 0
            tickets_to_add = []
            
            # Regla de Asignación: NO sobrescribir si ya tiene responsable
            for ticket in tickets_qs:
                if not ticket.usuario_responsable and ticket.falla_reportada and ticket.falla_reportada.usuario_responsable:
                    ticket.usuario_responsable = ticket.falla_reportada.usuario_responsable
                    ticket.save(update_fields=['usuario_responsable'])
                    count_assigned += 1
                
                tickets_to_add.append(ticket)
            
            if tickets_to_add:
                cluster.tickets.add(*tickets_to_add)
            
            messages.success(request, f"{msg_prefix} Se procesaron {len(tickets_to_add)} tickets y se asignaron {count_assigned} responsables.")
            return redirect('callcenter:cluster_tickets', cluster_id=cluster.id)

    return render(request, 'callcenter/wizard_cluster.html', {
        'departamentos': departamentos,
        'title': 'Wizard de Clusterización de Tickets',
        'now': now_str,
        'existing_cluster': existing_cluster,
        'selected_depto': existing_cluster.departamento if existing_cluster else None
    })

@staff_member_required
@mobile_permission_required('tiempo_acordado')
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


def _generate_tiempo_acordado_pdf_binary(acuerdo, force_empty_signatures=False):
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
            'FIRMA_RESPONSABLE': get_base64_image_tag(None if force_empty_signatures else acuerdo.firma_responsable, "RESPONSABLE"),
            'FIRMA_ENLACE': get_base64_image_tag(None if force_empty_signatures else acuerdo.firma_enlace, "ENLACE"),
            # Variaciones por si la plantilla usa nombres cortos
            'firma_resp': get_base64_image_tag(None if force_empty_signatures else acuerdo.firma_responsable, "RESPONSABLE_V"),
            'firma_enl': get_base64_image_tag(None if force_empty_signatures else acuerdo.firma_enlace, "ENLACE_V"),
            'FIRMA_R': get_base64_image_tag(None if force_empty_signatures else acuerdo.firma_responsable, "RESPONSABLE_V2")
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
        firma_r = "" if force_empty_signatures else (acuerdo.firma_responsable or "")
        firma_e = "" if force_empty_signatures else (acuerdo.firma_enlace or "")
        
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
    
    # Si se pide formato manual, forzar firmas vacías
    force_empty = request.GET.get('manual') == '1'
    data, filename, content_type = _generate_tiempo_acordado_pdf_binary(acuerdo, force_empty_signatures=force_empty)
    
    if force_empty:
        filename = f"Plantilla_Manual_Acuerdo_{acuerdo.id}.pdf"
    
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
            acuerdo.enviado = True
            acuerdo.save(update_fields=['enviado'])
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
    # Limpiar ID de posibles comas de formateo regional
    cluster_id = int(str(cluster_id).replace(',', ''))
    
    import json
    from .models import GrupoTicket, SolicitudTicket
    from django.utils import timezone
    
    try:
        data = json.loads(request.body)
        id_solicitud = data.get('id_solicitud')
        solicitante = data.get('solicitante', 'Manual')
        descripcion = data.get('descripcion', 'Sin descripción')
        es_interno = data.get('es_interno', False)
        
        if not id_solicitud:
            return JsonResponse({'success': False, 'error': 'ID de Solicitud es requerido'})
            
        cluster = get_object_or_404(GrupoTicket, id=cluster_id)
        
        # Crear el ticket
        ticket, created = SolicitudTicket.objects.get_or_create(
            id_solicitud=id_solicitud,
            defaults={
                'solicitante': solicitante,
                'solicitud_descripcion': descripcion,
                'fecha_solicitud': timezone.now(),
                'es_interno': es_interno
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
        
    search_q = Q(folio__icontains=q) | Q(solicitud_descripcion__icontains=q)
    if q.isdigit():
        search_q |= Q(id_solicitud=q)
    
    tickets = SolicitudTicket.objects.filter(search_q)[:10]
    
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

@csrf_exempt
def verify_correo_cierre_ajax(request, ticket_id):
    """
    AJAX: Verifica si el correo de cierre fue enviado mediante Power Automate.
    Envía POST a Power Automate con el texto del ticket y actualiza el campo correo_cierre.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)

    ticket_id = int(str(ticket_id).replace(',', ''))
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)

    payload = {
        "folio": str(ticket.folio or ticket.id_solicitud),
        "descripcion": (ticket.solicitud_descripcion or "").replace('\n', ' '),
        "falla": str(ticket.falla_descripcion or ""),
        "diagnostico": (ticket.diagnostico or "").replace('\n', ' '),
        "actividades": (ticket.actividades or "").replace('\n', ' '),
        "observaciones": (ticket.observaciones or "").replace('\n', ' '),
        "solicitante": str(ticket.solicitante or ""),
        "servicio": str(ticket.servicio or ""),
        "ubicacion": str(ticket.area or ""),
    }

    url_power_automate = "https://ce675e3ed2704594af019ed8d7d5f6.d7.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/205583600db14b76903401412d892f84/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=id_YHFshTRVSbjxUeImzeLg5broSX2g2yvPjOer8gUs"

    logger.info(f"Verificando correo de cierre para ticket {ticket.folio} via Power Automate...")

    try:
        response = requests.post(url_power_automate, json=payload, timeout=30)
        if response.status_code in [200, 202]:
            email_html = None
            try:
                body_data = response.json()
                if isinstance(body_data, dict):
                    email_html = body_data.get('email_html') or body_data.get('html') or body_data.get('content')
                    if not email_html and 'found' in body_data:
                        email_html = body_data.get('email_html')
                else:
                    email_html = str(body_data)
            except (json.JSONDecodeError, ValueError):
                email_html = response.text if response.text.strip() else None

            if email_html:
                ticket.correo_cierre = True
                ticket.save(update_fields=['correo_cierre'])
                logger.info(f"Correo de cierre ENCONTRADO para ticket {ticket.folio}")
                return JsonResponse({
                    'success': True,
                    'correo_cierre': True,
                    'email_html': email_html,
                    'message': 'SI SE ENCONTRO un correo de cierre'
                })
            else:
                logger.warning(f"Power Automate no devolvió HTML para ticket {ticket.folio}")
                return JsonResponse({
                    'success': False,
                    'correo_cierre': False,
                    'message': 'Power Automate respondió OK pero sin contenido HTML'
                })
        else:
            logger.warning(f"Power Automate respondió con código {response.status_code} para ticket {ticket.folio}")
            return JsonResponse({
                'success': False,
                'correo_cierre': False,
                'message': f'Power Automate respondió con código {response.status_code}'
            })
    except Exception as e:
        logger.error(f"Error verificando correo de cierre para ticket {ticket.folio}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'correo_cierre': False,
            'message': str(e)
        })

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
@mobile_permission_required('tiempo_acordado')
def mobile_crear_tiempo_acordado_view(request, pk=None):
    """Vista Fiori para crear o editar un Tiempo Acordado desde la App."""
    from .models import SolicitudTicket, Enlace, Institucion, TiempoAcordado, TiempoAcordadoTarea, CronogramaPredefinido
    from activos.models import Ubicacion
    from django.utils import timezone
    from datetime import datetime
    
    acuerdo = None
    if pk:
        acuerdo = get_object_or_404(TiempoAcordado, pk=pk)
        # Solo permitir editar si es BORRADOR
        if acuerdo.estatus != 'BORRADOR':
            return JsonResponse({'success': False, 'error': 'Solo se pueden editar acuerdos en estado BORRADOR.'}, status=403)

    if request.method == 'POST':
        try:
            # 1. Crear o Actualizar el Acuerdo Base
            ticket_id = request.POST.get('ticket', '').replace(',', '')
            enlace_id = request.POST.get('enlace', '').replace(',', '')
            ubicacion_id = request.POST.get('ubicacion', '').replace(',', '')
            if not ubicacion_id and acuerdo:
                ubicacion_id = acuerdo.ubicacion_id
            fecha_final_str = request.POST.get('fecha_solucion_final')
            
            if not ticket_id or not enlace_id or not fecha_final_str:
                return JsonResponse({'success': False, 'error': 'Ticket, Enlace y Fecha Final son requeridos.'})

            from django.utils.dateparse import parse_datetime

            def safe_parse_dt(dt_str):
                if not dt_str: return None
                try:
                    dt = parse_datetime(dt_str)
                    if not dt:
                        # Reintento manual si parse_datetime falla (algunos formatos ISO)
                        dt = datetime.fromisoformat(dt_str)
                    if dt and timezone.is_naive(dt):
                        return timezone.make_aware(dt)
                    return dt
                except:
                    return None

            # Datos base
            fecha_final = safe_parse_dt(fecha_final_str)
            if not fecha_final:
                return JsonResponse({'success': False, 'error': f'Formato de fecha final inválido: {fecha_final_str}'})

            datos_acuerdo = {
                'ticket_id': ticket_id,
                'enlace_id': enlace_id,
                'ubicacion_id': ubicacion_id if ubicacion_id else None,
                'motivo_extension': request.POST.get('motivo_extension', ''),
                'solucion_provisional': request.POST.get('solucion_provisional', ''),
                'observaciones': request.POST.get('observaciones', ''),
                'fecha_solucion_final': fecha_final,
                'firma_enlace': request.POST.get('firma_enlace') or (acuerdo.firma_enlace if acuerdo else None),
                'firma_responsable': request.POST.get('firma_responsable') or (acuerdo.firma_responsable if acuerdo else None)
            }

            if acuerdo:
                # Actualizar existente
                for key, value in datos_acuerdo.items():
                    setattr(acuerdo, key, value)
                acuerdo.save()
            else:
                # Crear nuevo
                acuerdo = TiempoAcordado.objects.create(
                    usuario_creador=request.user,
                    estatus='BORRADOR',
                    **datos_acuerdo
                )
            
            # 2. Procesar Tareas
            if pk:
                acuerdo.tareas.all().delete()

            tareas_desc = request.POST.getlist('tarea_descripcion[]')
            tareas_inicio = request.POST.getlist('tarea_inicio[]')
            tareas_fin = request.POST.getlist('tarea_fin[]')
            
            objs_tareas = []
            for i in range(len(tareas_desc)):
                if tareas_desc[i].strip() and tareas_inicio[i] and tareas_fin[i]:
                    t_ini = safe_parse_dt(tareas_inicio[i])
                    t_fin = safe_parse_dt(tareas_fin[i])
                    
                    if t_ini and t_fin:
                        objs_tareas.append(TiempoAcordadoTarea(
                            tiempo_acordado=acuerdo,
                            descripcion=tareas_desc[i],
                            fecha_inicio=t_ini,
                            fecha_fin=t_fin
                        ))
            
            if objs_tareas:
                TiempoAcordadoTarea.objects.bulk_create(objs_tareas)
                
            return JsonResponse({'success': True, 'id': acuerdo.id})
        except Exception as e:
            import traceback
            logger.error(f"Error procesando Tiempo Acordado móvil: {e}\n{traceback.format_exc()}")
            return JsonResponse({'success': False, 'error': str(e)})

    # Contexto para el GET
    # Intentar obtener ticket de los parámetros GET para pre-vínculo
    ticket = None
    ticket_id = request.GET.get('ticket')
    if ticket_id:
        try:
            ticket = SolicitudTicket.objects.get(id=ticket_id)
        except (SolicitudTicket.DoesNotExist, ValueError):
            pass

    # Solo mostramos ubicaciones que son de tipo EDIFICIO para el primer selector
    edificios = Ubicacion.objects.filter(tipo='EDIFICIO').order_by('nombre')
    enlaces = Enlace.objects.select_related('institucion', 'ubicacion').all().order_by('nombre')
    
    # Cronogramas Predefinidos
    cronogramas_templates = CronogramaPredefinido.objects.all().order_by('nombre')
    
    return render(request, 'callcenter/mobile_crear_tiempo_acordado.html', {
        'acuerdo': acuerdo,
        'ticket': ticket or (acuerdo.ticket if acuerdo else None),
        'enlaces': enlaces,
        'edificios': edificios,
        'cronogramas_templates': cronogramas_templates,
        'title': 'Editar Tiempo Acordado' if acuerdo else 'Nuevo Tiempo Acordado',
        'now': timezone.localtime(timezone.now())
    })

@staff_member_required
def api_get_cronograma_items_ajax(request, pk):
    """Retorna los items de un cronograma predefinido para precargar en el móvil."""
    from .models import CronogramaPredefinido
    crono = get_object_or_404(CronogramaPredefinido, pk=pk)
    
    items_data = []
    # Ordenar por número para asegurar secuencia lógica
    for item in crono.items.all().order_by('numero'):
        items_data.append({
            'id': item.id,
            'numero': item.numero,
            'descripcion': item.descripcion,
            'duracion_dias': item.duracion_dias,
            'predecesores_numeros': list(item.predecesores.values_list('numero', flat=True))
        })
    
    return JsonResponse({'success': True, 'items': items_data})

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
        
    # Si es edición, calcular fechas relativas para el GANTT
    gantt_data = []
    if instance:
        from django.utils import timezone
        from datetime import timedelta
        base_date = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
        items = list(instance.items.all().prefetch_related('predecesores'))
        
        # Mapeo de fechas para cálculos rápidos
        fechas_finales = {} # {id: end_date}
        
        # Procesar items en orden (asumimos numero refleja orden lógico)
        for item in items:
            start_date = base_date
            # Si tiene predecesores, su inicio es el máximo de sus finales
            preds = item.predecesores.all()
            if preds:
                fechas_preds = [fechas_finales.get(p.id, base_date) for p in preds]
                start_date = max(fechas_preds)
            
            end_date = start_date + timedelta(days=item.duracion_dias)
            fechas_finales[item.id] = end_date
            
            # Formatear para Frappe Gantt (YYYY-MM-DD)
            gantt_data.append({
                'id': str(item.id),
                'name': f"{item.numero}. {item.descripcion}",
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d'),
                'progress': 0,
                'dependencies': ", ".join([str(p.id) for p in preds])
            })

    import json
    context = {
        'form': form,
        'formset': formset,
        'instance': instance,
        'title': "Editar Cronograma" if instance else "Nuevo Cronograma",
        'gantt_data_json': json.dumps(gantt_data)
    }
    return render(request, 'callcenter/cronograma_predefinido_form.html', context)


@login_required
def cronograma_predefinido_detalle_view(request, pk):
    """
    Vista de solo lectura para visualizar el cronograma y su GANTT.
    """
    instance = get_object_or_404(CronogramaPredefinido, pk=pk)
    
    # Cálculo de GANTT (igual que en Edit)
    from django.utils import timezone
    from datetime import timedelta
    import json
    
    base_date = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
    items = list(instance.items.all().prefetch_related('predecesores').order_by('numero'))
    
    gantt_data = []
    fechas_finales = {}
    for item in items:
        start_date = base_date
        preds = item.predecesores.all()
        if preds:
            fechas_preds = [fechas_finales.get(p.id, base_date) for p in preds]
            start_date = max(fechas_preds)
        
        end_date = start_date + timedelta(days=item.duracion_dias)
        fechas_finales[item.id] = end_date
        
        gantt_data.append({
            'id': str(item.id),
            'name': f"{item.numero}. {item.descripcion}",
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d'),
            'progress': 0,
            'dependencies': ", ".join([str(p.id) for p in preds])
        })

    context = {
        'instance': instance,
        'items': items,
        'gantt_data_json': json.dumps(gantt_data),
        'title': f"Detalle: {instance.nombre}"
    }
    return render(request, 'callcenter/cronograma_predefinido_detalle.html', context)

@staff_member_required
def cronograma_predefinido_lista_view(request):
    """Lista simple de cronogramas predefinidos."""
    from .models import CronogramaPredefinido
    from django.shortcuts import render
    cronogramas = CronogramaPredefinido.objects.all().select_related('departamento')
    return render(request, 'callcenter/cronograma_predefinido_lista.html', {'cronogramas': cronogramas})

@staff_member_required
def get_diagnosticos_by_falla_ajax(request):
    """
    Vista AJAX para obtener los diagnósticos asociados a una falla (y sus ancestros).
    """
    falla_id = request.GET.get('falla_id')
    if not falla_id:
        return JsonResponse([], safe=False)
    
    from .models import FallaTicket
    falla = get_object_or_404(FallaTicket, id=falla_id)
    diagnosticos = falla.get_all_diagnosticos()
    
    data = [{'id': d.id, 'nombre': d.nombre} for d in diagnosticos]
    return JsonResponse(data, safe=False)

@staff_member_required
def ticket_detail_ajax(request, ticket_id):
    """
    Vista AJAX que devuelve los detalles completos de un ticket en formato JSON
    para el modal SAP Fiori del cluster de tickets.
    """
    ticket_id = int(str(ticket_id).replace(',', ''))
    ticket = get_object_or_404(
        SolicitudTicket.objects.select_related(
            'activo', 'activo__modelo', 'activo__modelo__marca',
            'ubicacion', 'usuario_responsable', 'falla_reportada',
            'diagnostico_reportado', 'proveedor_deductiva'
        ),
        id=ticket_id
    )

    # Tiempos Acordados
    tiempos = []
    for ta in ticket.tiempos_acordados.all().order_by('-creado_en')[:5]:
        tiempos.append({
            'folio': str(ta.folio_ta) if hasattr(ta, 'folio_ta') else f"TA-{ta.id}",
            'fecha_limite': ta.fecha_solucion_final.strftime('%d/%m/%Y %H:%M') if ta.fecha_solucion_final else '—',
            'motivo': (ta.motivo_extension or '')[:120],
            'creado_en': ta.creado_en.strftime('%d/%m/%Y %H:%M') if ta.creado_en else '—',
        })

    # Restricción de acceso
    restriccion_data = None
    try:
        ra = ticket.restriccion_acceso
        restriccion_data = {
            'folio': str(ra.folio_ra),
            'horas': str(ra.horas_restriccion),
            'creado_en': ra.creado_en.strftime('%d/%m/%Y %H:%M') if ra.creado_en else '—',
        }
    except Exception:
        restriccion_data = None

    # Evidencias (solo contar y primeras 6)
    evidencias = []
    for ev in ticket.evidencias.all().order_by('-id')[:6]:
        evidencias.append({
            'url': ev.archivo.url if ev.archivo else '',
            'descripcion': ev.descripcion or '',
            'es_imagen': any(ev.archivo.name.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']) if ev.archivo else False,
        })

    def fmt(dt):
        if not dt:
            return '—'
        from django.utils import timezone
        return timezone.localtime(dt).strftime('%d/%m/%Y %H:%M')

    data = {
        # Identificadores
        'id': ticket.id,
        'id_solicitud': str(ticket.id_solicitud),
        'folio': ticket.folio or str(ticket.id_solicitud),
        'es_interno': ticket.es_interno,

        # Estado
        'abierto': not bool(ticket.fecha_cierre),
        'cierre_enviado': bool(ticket.cierre_enviado),
        'correo_cierre': bool(ticket.correo_cierre),

        # Personas
        'solicitante': ticket.solicitante or '—',
        'responsable': ticket.responsable or '—',
        'usuario_responsable': ticket.usuario_responsable.get_full_name() if ticket.usuario_responsable else '—',

        # Clasificación
        'servicio': ticket.servicio or '—',
        'subservicio': ticket.subservicio or '—',
        'unidad': ticket.unidad or '—',
        'area': ticket.area or '—',
        'grupo': ticket.grupo or '—',
        'nivel': ticket.nivel or '—',

        # Tipo y recepción
        'tipo_recepcion': ticket.tipo_recepcion or '—',
        'tipo_solicitud': ticket.tipo_solicitud or '—',

        # Fechas
        'fecha_solicitud': fmt(ticket.fecha_solicitud),
        'fecha_tipo_recepcion': fmt(ticket.fecha_tipo_recepcion),
        'fecha_suspension': fmt(ticket.fecha_suspension),
        'fecha_cierre': fmt(ticket.fecha_cierre),

        # Descripciones
        'solicitud_descripcion': ticket.solicitud_descripcion or '',
        'falla_descripcion': ticket.falla_descripcion or '',
        'falla_clasificacion': ticket.falla_clasificacion or '—',
        'clasificacion_falla_final': ticket.clasificacion_falla_final or '—',

        # Seguimiento técnico
        'diagnostico': ticket.diagnostico or '',
        'actividades': ticket.actividades or '',
        'observaciones': ticket.observaciones or '',
        'comentarios_internos': ticket.comentarios_internos or '',

        # Activo
        'activo_nombre': ticket.activo.nombre if ticket.activo else '—',
        'activo_codigo': ticket.activo.codigo_interno if ticket.activo else '—',
        'activo_serie': ticket.activo.serie if ticket.activo else '—',

        # Ubicación
        'ubicacion_nombre': ticket.ubicacion.ruta_completa if ticket.ubicacion and hasattr(ticket.ubicacion, 'ruta_completa') else (str(ticket.ubicacion) if ticket.ubicacion else '—'),

        # Financiero
        'deductiva': str(ticket.deductiva or '0.00'),
        'proveedor_deductiva': ticket.proveedor_deductiva.nombre if ticket.proveedor_deductiva else '—',

        # Falla Catálogo
        'falla_reportada_id': ticket.falla_reportada_id,
        'falla_reportada': str(ticket.falla_reportada) if ticket.falla_reportada else '—',

        # Diagnóstico Catálogo
        'diagnostico_reportado_id': ticket.diagnostico_reportado_id,
        'diagnostico_reportado_nombre': ticket.diagnostico_reportado.nombre if ticket.diagnostico_reportado else '—',
        'diagnostico_reportado': str(ticket.diagnostico_reportado) if ticket.diagnostico_reportado else '—',

        # Relaciones
        'tiempos_acordados': tiempos,
        'restriccion': restriccion_data,
        'evidencias': evidencias,
        'num_evidencias': ticket.evidencias.count(),

        # URLs de acción rápida
        # Historial
        'historial': [{
            'accion': h.accion,
            'accion_display': h.get_accion_display(),
            'usuario': h.usuario.get_full_name() or h.usuario.username if h.usuario else '—',
            'descripcion': h.descripcion,
            'creado_en': fmt(h.creado_en),
        } for h in ticket.historial.all().order_by('-creado_en')[:50]],

        # URLs de acción rápida
        'url_admin': f'/admin/callcenter/solicitudticket/{ticket.id}/change/',
        'url_cierre_visual': f'/callcenter/ticket/{ticket.id}/cierre-visual/',
        'url_sync': f'/admin/callcenter/solicitudticket/{ticket.id}/sync-singular/',
        'url_power_automate': f'/callcenter/ticket/{ticket.id}/enviar-power-automate/',

        # Departamento actual
        'departamento_id': ticket.falla_reportada.departamento_responsable_id if ticket.falla_reportada and ticket.falla_reportada.departamento_responsable_id else None,
        'departamento_nombre': ticket.falla_reportada.departamento_responsable.nombre if ticket.falla_reportada and ticket.falla_reportada.departamento_responsable else '—',

        # Listas para el formulario de edición
        'departamentos': list(
            Departamento.objects.all().order_by('nombre')
            .values('id', 'nombre')
        ),
        'fallas_por_departamento': {
            str(did): list(
                FallaTicket.objects.filter(departamento_responsable_id=did)
                .order_by('nombre')
                .values('id', 'nombre')
            )
            for did in Departamento.objects.all().values_list('id', flat=True)
        },
        'proveedores': list(
            __import__('mantenimiento.models', fromlist=['Empresa'])
            .Empresa.objects.filter(activo=True).order_by('nombre')
            .values('id', 'nombre')
        ),
        'usuarios': list(
            __import__('django.contrib.auth', fromlist=['get_user_model'])
            .get_user_model().objects.filter(is_active=True).order_by('first_name', 'username')
            .values('id', 'first_name', 'last_name', 'username')
        ),
        'proveedor_deductiva_id': ticket.proveedor_deductiva_id,
        'usuario_responsable_id': ticket.usuario_responsable_id,
        'fecha_cierre_raw': ticket.fecha_cierre.astimezone().strftime('%Y-%m-%dT%H:%M') if ticket.fecha_cierre else '',
    }

    return JsonResponse(data)


@staff_member_required
@require_POST
@csrf_exempt
def ticket_quick_edit_ajax(request, ticket_id):
    """
    Guarda los campos editables del ticket desde el modal SAP Fiori del cluster.
    Campos admitidos: fecha_cierre, diagnostico, actividades, observaciones,
    comentarios_internos, deductiva, proveedor_deductiva, usuario_responsable,
    clasificacion_falla_final.
    """
    import json
    from decimal import Decimal, InvalidOperation
    from django.utils import timezone
    from datetime import datetime

    ticket_id = int(str(ticket_id).replace(',', ''))
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        body = request.POST

    # Fecha cierre
    fecha_cierre_str = body.get('fecha_cierre', '').strip()
    if fecha_cierre_str:
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                dt = datetime.strptime(fecha_cierre_str, fmt)
                ticket.fecha_cierre = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                break
            except ValueError:
                pass
    else:
        ticket.fecha_cierre = None

    # Campos de texto
    ticket.diagnostico = body.get('diagnostico', ticket.diagnostico or '')
    ticket.actividades = body.get('actividades', ticket.actividades or '')
    ticket.observaciones = body.get('observaciones', ticket.observaciones or '')
    ticket.comentarios_internos = body.get('comentarios_internos', ticket.comentarios_internos or '')
    ticket.clasificacion_falla_final = body.get('clasificacion_falla_final', ticket.clasificacion_falla_final or '')

    # Diagnóstico del Catálogo
    diagnostico_reportado_id = body.get('diagnostico_reportado', '')
    if diagnostico_reportado_id:
        from .models import DiagnosticoTicket
        ticket.diagnostico_reportado = DiagnosticoTicket.objects.filter(id=diagnostico_reportado_id).first()
    else:
        ticket.diagnostico_reportado = None

    # Deductiva
    deductiva_raw = body.get('deductiva', '')
    if deductiva_raw != '':
        try:
            ticket.deductiva = Decimal(str(deductiva_raw).replace(',', ''))
        except (InvalidOperation, ValueError):
            pass

    # Proveedor
    proveedor_id = body.get('proveedor_deductiva', '')
    if proveedor_id:
        from mantenimiento.models import Empresa
        ticket.proveedor_deductiva = Empresa.objects.filter(id=proveedor_id).first()
    else:
        ticket.proveedor_deductiva = None

    # Usuario responsable
    usuario_id = body.get('usuario_responsable', '')
    if usuario_id:
        from django.contrib.auth import get_user_model
        ticket.usuario_responsable = get_user_model().objects.filter(id=usuario_id).first()
    else:
        ticket.usuario_responsable = None

    # Falla reportada (cambio de departamento)
    falla_id = body.get('falla_reportada', '')
    if falla_id:
        from .models import FallaTicket
        ticket.falla_reportada = FallaTicket.objects.filter(id=falla_id).first()

    # Correo de cierre
    if 'correo_cierre' in body:
        ticket.correo_cierre = bool(body.get('correo_cierre'))

    ticket.save()
    return JsonResponse({'success': True, 'message': 'Ticket actualizado correctamente.'})

@login_required
@mobile_permission_required('mis_avisos')

def mobile_ticket_detalle_view(request, pk):
    """
    Vista premium y optimizada para móviles para visualizar el detalle de un ticket.
    """
    ticket = get_object_or_404(
        SolicitudTicket.objects.select_related('activo', 'ubicacion', 'usuario_responsable'), 
        pk=pk
    )
    
    # Obtener evidencias relacionadas
    evidencias = ticket.evidencias.all().order_by('-fecha_carga')
    
    # Obtener Tiempos Acordados relacionados
    tiempos_acordados = ticket.tiempos_acordados.all().order_by('-creado_en')
    
    # Obtener Restricción de Acceso si existe
    restriccion = getattr(ticket, 'restriccion_acceso', None)
    
    context = {
        'ticket': ticket,
        'evidencias': evidencias,
        'tiempos_acordados': tiempos_acordados,
        'restriccion': restriccion,
        'title': f"Ticket {ticket.folio or ticket.id_solicitud}"
    }
    return render(request, 'callcenter/mobile_ticket_detalle.html', context)

@staff_member_required
@require_POST
@csrf_exempt
def save_comentario_interno_ajax(request, ticket_id):
    """
    Guarda o actualiza el comentario interno de un ticket.
    """
    # Limpiar ID de posibles comas de formateo regional
    ticket_id = int(str(ticket_id).replace(',', ''))
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
    
    try:
        data = json.loads(request.body)
        comentario = data.get('comentario_interno', '')
    except:
        comentario = request.POST.get('comentario_interno', '')

    ticket.comentarios_internos = comentario
    ticket.save(update_fields=['comentarios_internos'])

    return JsonResponse({
        'success': True,
        'message': 'Comentario interno guardado con éxito.',
        'comentario': ticket.comentarios_internos
    })

@staff_member_required
@require_POST
@csrf_exempt
def toggle_ticket_interno_ajax(request, ticket_id):
    """
    Alterna el estado del campo es_interno de un ticket.
    """
    # Limpiar ID de posibles comas de formateo regional
    ticket_id = int(str(ticket_id).replace(',', ''))
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
    
    ticket.es_interno = not ticket.es_interno
    ticket.save(update_fields=['es_interno'])
    
    estado_str = "interno" if ticket.es_interno else "externo"
    return JsonResponse({
        'success': True,
        'message': f'El ticket se ha marcado como {estado_str}.',
        'es_interno': ticket.es_interno
    })

@staff_member_required
@require_POST
@csrf_exempt
def create_restriccion_acceso_ajax(request, ticket_id):
    """
    Crea una Restricción de Acceso vinculada a un ticket cerrado.
    Folio: RA-DEPT-2026-001
    Horas: Calculadas según horario hábil (7-23h, 16h/día).
    """
    from .utils import calcular_horas_habiles
    
    # Limpiar ID de posibles comas de formateo regional
    ticket_id = int(str(ticket_id).replace(',', ''))
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
    
    if not ticket.fecha_cierre:
        return JsonResponse({'success': False, 'message': 'El ticket debe estar cerrado para crear una restricción.'}, status=400)
    
    if hasattr(ticket, 'restriccion_acceso'):
        return JsonResponse({'success': False, 'message': 'Este ticket ya tiene una restricción de acceso asociada.'}, status=400)

    try:
        data = json.loads(request.body)
        firma = data.get('firma')
        firma_tecnico = data.get('firma_tecnico')
    except:
        firma = request.POST.get('firma')
        firma_tecnico = request.POST.get('firma_tecnico')

    # 1. Resolver Departamento para el folio
    dept_nombre = "INST" # Fallback
    if hasattr(request.user, 'perfil') and request.user.perfil.departamento:
        # Tomar las primeras 4 letras en mayúsculas, quitando caracteres no alfanuméricos
        raw_dept = request.user.perfil.departamento.nombre
        dept_nombre = "".join(filter(str.isalnum, raw_dept))[:4].upper()
    
    anio = timezone.now().year
    prefix = f"RA-{dept_nombre}-{anio}-"
    
    # Obtener el correlativo anual/dept
    ultima_ra = RestriccionAcceso.objects.filter(folio_ra__startswith=prefix).order_by('folio_ra').last()
    if ultima_ra:
        try:
            ultimo_num_str = ultima_ra.folio_ra.split('-')[-1]
            nuevo_num = int(ultimo_num_str) + 1
        except:
            nuevo_num = 1
    else:
        nuevo_num = 1
    
    folio = f"{prefix}{str(nuevo_num).zfill(3)}"
    
    # 2. Calcular Horas (7-23h, excluyendo feriados/findes)
    desde = ticket.fecha_solicitud
    hasta = ticket.fecha_cierre
    
    horas = calcular_horas_habiles(desde, hasta)
    
    # 3. Guardar Registro
    ra = RestriccionAcceso.objects.create(
        ticket=ticket,
        folio_ra=folio,
        fecha_restriccion=desde,
        fecha_reprogramacion=hasta,
        horas_restriccion=horas,
        firma_usuario=firma,
        firma_tecnico=firma_tecnico,
        usuario_creador=request.user
    )
    
    return JsonResponse({
        'success': True, 
        'folio': ra.folio_ra,
        'horas': float(ra.horas_restriccion),
        'id': ra.id
    })

@staff_member_required
def export_restriccion_acceso_pdf(request, pk):
    """
    Genera un PDF formal para una Restricción de Acceso.
    """
    from .models import RestriccionAcceso
    ra = get_object_or_404(RestriccionAcceso, pk=pk)
    ticket = ra.ticket
    
    html_content = render_to_string('callcenter/restriccion_acceso_pdf.html', {
        'ra': ra,
        'ticket': ticket,
        'ahora': timezone.now(),
        'user': request.user,
    }, request=request)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            page.set_content(html_content, wait_until='networkidle')
            pdf_bytes = page.pdf(format="A4", print_background=True)
            browser.close()
            
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            filename = f"Restriccion_{ra.folio_ra}_{ticket.folio or ticket.id_solicitud}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    except Exception as e:
        logger.error(f"Error generando PDF para Restricción {ra.id}: {e}")
        return HttpResponse(f"Error al generar el PDF: {e}", status=500)

@staff_member_required
def exportar_solicitudticket_pdf(request, ticket_id):
    """
    Exporta un ticket individual a PDF como ficha técnica.
    """
    ticket_id = int(ticket_id.replace(',', '').replace('.', ''))
    ticket = get_object_or_404(SolicitudTicket.objects.select_related(
        'activo', 'ubicacion', 'falla_reportada', 'diagnostico_reportado', 'usuario_responsable', 'proveedor_deductiva'
    ), id=ticket_id)

    evidencias = EvidenciaTicket.objects.filter(ticket=ticket)

    logo_dcc_b64 = ""
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'activos', 'static', 'activos', 'img', 'logo_operadora_cc.png')
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as image_file:
            logo_dcc_b64 = base64.b64encode(image_file.read()).decode('utf-8')

    html_content = render_to_string('callcenter/solicitudticket_export_pdf.html', {
        'ticket': ticket,
        'evidencias': evidencias,
        'ahora': timezone.now(),
        'user': request.user,
        'logo_dcc_b64': logo_dcc_b64,
    }, request=request)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            page.set_content(html_content, wait_until='networkidle')
            pdf_bytes = page.pdf(format="A4", print_background=True)
            browser.close()

            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            filename = f"Ticket_{ticket.folio or ticket.id_solicitud}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    except Exception as e:
        logger.error(f"Error generando PDF para ticket {ticket.id}: {e}")
        return HttpResponse(f"Error al generar el PDF: {e}", status=500)


@csrf_exempt
def webhook_ticket_vector_callback(request):
    """
    Callback para n8n: Recibe el vector de embedding y el cluster asignado.
    Payload esperado:
    {
        "ticket_id": 123,
        "embedding": [0.12, 0.45, ...],
        "cluster_name": "Falla de Transformador" (opcional)
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        ticket_id = data.get('ticket_id')
        embedding = data.get('embedding')
        cluster_name = data.get('cluster_name')

        if not ticket_id or embedding is None:
            return JsonResponse({'error': 'ticket_id and embedding are required'}, status=400)

        from .models import SolicitudTicket, GrupoTicket
        ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
        
        # 1. Actualizar el vector
        ticket.embedding = embedding
        ticket.save(update_fields=['embedding'])
        
        # 2. Gestionar Clustering (GrupoTicket)
        if cluster_name:
            # Buscar o crear el grupo
            grupo, created = GrupoTicket.objects.get_or_create(
                descripcion__iexact=cluster_name.strip(),
                defaults={'descripcion': cluster_name.strip()}
            )
            # Vincular el ticket al grupo
            if not ticket.grupos.filter(id=grupo.id).exists():
                ticket.grupos.add(grupo)

        logger.info(f"Vector y cluster actualizados para ticket {ticket.folio or ticket.id_solicitud}")
        return JsonResponse({
            'success': True, 
            'ticket': ticket.folio or ticket.id_solicitud,
            'cluster_assigned': cluster_name if cluster_name else "N/A"
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error en webhook_ticket_vector_callback: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def vectorize_cluster_tickets_ajax(request, cluster_id):
    # Limpiar ID de posibles comas de formateo regional
    cluster_id = int(str(cluster_id).replace(',', ''))
    cluster = get_object_or_404(GrupoTicket, id=cluster_id)
    tickets = cluster.tickets.all()
    
    if not tickets.exists():
        return JsonResponse({'success': False, 'error': 'El cluster no tiene tickets.'})

    try:
        from .tasks import vectorize_ticket_n8n
        count = 0
        for ticket in tickets:
            # Forzamos el envío a n8n independientemente de si ya tiene embedding
            vectorize_ticket_n8n.delay(ticket.id)
            count += 1
            
        return JsonResponse({
            'success': True, 
            'message': f'Se han encolado {count} tickets para vectorización IA.'
        })
    except Exception as e:
        logger.error(f"Error al encolar vectorización de cluster {cluster_id}: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@staff_member_required
@require_POST
def add_tickets_to_cluster_ajax(request, cluster_id):
    """Agrega tickets existentes a un cluster mediante una lista de folios (pegado)."""
    # Limpiar ID de posibles comas de formateo regional
    cluster_id = int(str(cluster_id).replace(',', ''))
    cluster = get_object_or_404(GrupoTicket, id=cluster_id)
    
    folios_raw = request.POST.get('folios', '').strip()
    if not folios_raw:
        return JsonResponse({'success': False, 'error': 'No se proporcionaron folios.'})
    
    # Parsear folios (separados por comas, espacios o saltos de línea)
    import re
    folios = list(set([f.strip() for f in re.split(r'[\s,]+', folios_raw) if f.strip()]))
    
    if not folios:
        return JsonResponse({'success': False, 'error': 'No se encontraron folios válidos en el texto.'})
    
    try:
        from django.db.models import Q
        # Buscar tickets
        tickets_encontrados = SolicitudTicket.objects.filter(
            Q(folio__in=folios) | Q(folio__iexact=folios) # __in es más eficiente para listas
        )
        
        # Si falló la búsqueda masiva exacta (por temas de case sensitivity en algunos DBs)
        # o si queremos ser más exhaustivos:
        if tickets_encontrados.count() < len(folios):
            query = Q()
            for f in folios:
                query |= Q(folio__iexact=f)
            tickets_encontrados = SolicitudTicket.objects.filter(query)

        count_antes = cluster.tickets.count()
        cluster.tickets.add(*tickets_encontrados)
        count_despues = cluster.tickets.count()
        
        vinculados = count_despues - count_antes
        
        return JsonResponse({
            'success': True,
            'message': f'Se procesaron {len(folios)} folios. Se encontraron {tickets_encontrados.count()} tickets y se vincularon {vinculados} nuevos al cluster.'
        })
    except Exception as e:
        logger.error(f"Error vinculando folios a cluster {cluster_id}: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@staff_member_required
@mobile_permission_required('mis_avisos')
def mobile_ticket_cierre_view(request, pk):
    """Vista optimizada para cerrar un ticket desde dispositivos móviles."""
    from django.utils import timezone
    from datetime import datetime
    
    ticket = get_object_or_404(SolicitudTicket, pk=pk)
    
    if request.method == 'POST':
        # Procesar cierre
        ticket.diagnostico = request.POST.get('diagnostico', '')
        ticket.actividades = request.POST.get('actividades', '')
        
        fecha_cierre_str = request.POST.get('fecha_cierre')
        if fecha_cierre_str:
            try:
                dt = datetime.strptime(fecha_cierre_str, '%Y-%m-%dT%H:%M')
                ticket.fecha_cierre = timezone.make_aware(dt)
            except:
                ticket.fecha_cierre = timezone.now()
        else:
            ticket.fecha_cierre = timezone.now()
            
        ticket.save()
        
        from django.http import JsonResponse
        return JsonResponse({'success': True})

    context = {
        'ticket': ticket,
        'title': f'Cerrar Ticket {ticket.folio or ticket.id_solicitud}',
        'now': timezone.now().strftime('%Y-%m-%dT%H:%M')
    }
    return render(request, 'callcenter/mobile_ticket_cierre.html', context)

@staff_member_required
def import_fallatickets_process(request):
    """
    Vista para manejar el flujo de importación asíncrona del catálogo de fallas de tickets.
    """
    from django.core.cache import cache
    from django.core.files.storage import default_storage
    from .tasks import import_fallatickets_task
    import os

    cache_key = f"import_fallatickets_progress_{request.user.id}"

    if request.method == 'GET':
        action = request.GET.get('action')
        if action == 'status':
            progress = cache.get(cache_key)
            return JsonResponse(progress or {'status': 'idle'})
        
        return render(request, 'admin/callcenter/fallaticket/import_background.html', {
            'title': 'Importación Asíncrona de Catálogo de Fallas'
        })

    if request.method == 'POST':
        # Paso 1: Subida de archivo y validación inicial (Verification Mode)
        if 'file' in request.FILES:
            file = request.FILES['file']
            file_path = default_storage.save(f'tmp/fallas_tickets_import_{request.user.id}.xlsx', file)
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            
            # Guardar ruta en cache para el siguiente paso
            cache.set(f"import_fallatickets_file_{request.user.id}", full_path, 3600)
            
            # Lanzar tarea en modo verificación
            import_fallatickets_task.delay(full_path, request.user.id, verification_mode=True)
            return JsonResponse({'status': 'started'})

        # Paso 2: Confirmación de importación real
        if request.POST.get('confirm') == 'true':
            full_path = cache.get(f"import_fallatickets_file_{request.user.id}")
            if not full_path or not os.path.exists(full_path):
                return JsonResponse({'status': 'error', 'message': 'Archivo no encontrado. Por favor suba el archivo de nuevo.'})
            
            # Lanzar tarea en modo real
            import_fallatickets_task.delay(full_path, request.user.id, verification_mode=False)
            return JsonResponse({'status': 'started'})

    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@staff_member_required
def import_diagnosticos_process(request):
    """
    Vista para manejar el flujo de importación asíncrona del catálogo de diagnósticos de tickets.
    """
    from django.core.cache import cache
    from django.core.files.storage import default_storage
    from .tasks import import_diagnosticos_task
    import os

    cache_key = f"import_diagnosticos_progress_{request.user.id}"

    if request.method == 'GET':
        action = request.GET.get('action')
        if action == 'status':
            progress = cache.get(cache_key)
            return JsonResponse(progress or {'status': 'idle'})
        
        return render(request, 'admin/callcenter/diagnosticoticket/import_background.html', {
            'title': 'Importación Asíncrona de Catálogo de Diagnósticos'
        })

    if request.method == 'POST':
        # Paso 1: Subida de archivo y validación inicial (Verification Mode)
        if 'file' in request.FILES:
            file = request.FILES['file']
            file_path = default_storage.save(f'tmp/diagnosticos_tickets_import_{request.user.id}.xlsx', file)
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            
            # Guardar ruta en cache para el siguiente paso
            cache.set(f"import_diagnosticos_file_{request.user.id}", full_path, 3600)
            
            # Lanzar tarea en modo verificación
            import_diagnosticos_task.delay(full_path, request.user.id, verification_mode=True)
            return JsonResponse({'status': 'started'})

        # Paso 2: Confirmación de importación real
        if request.POST.get('confirm') == 'true':
            full_path = cache.get(f"import_diagnosticos_file_{request.user.id}")
            if not full_path or not os.path.exists(full_path):
                return JsonResponse({'status': 'error', 'message': 'Archivo no encontrado. Por favor suba el archivo de nuevo.'})
            
            # Lanzar tarea en modo real
            import_diagnosticos_task.delay(full_path, request.user.id, verification_mode=False)
            return JsonResponse({'status': 'started'})

    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@staff_member_required
def get_dashboard_node_tickets_ajax(request):
    """
    Retorna el listado de tickets filtrado por nodo (Depto, Falla o Ubicación).
    """
    from django.template.loader import render_to_string
    from django.db.models import Q
    from core.models import Departamento
    from .models import FallaTicket
    from activos.models import Ubicacion
    
    depto_id = request.GET.get('depto_id')
    falla_id = request.GET.get('falla_id')
    ubicacion_id = request.GET.get('ubicacion_id')
    
    ticket_qs = get_filtered_ticket_qs(request)
    node_name = "Tickets Seleccionados"
    
    if depto_id and depto_id != '0':
        ticket_qs = ticket_qs.filter(falla_reportada__departamento_responsable_id=depto_id)
        try: node_name = Departamento.objects.get(id=depto_id).nombre
        except: pass
    elif depto_id == '0':
        ticket_qs = ticket_qs.filter(falla_reportada__departamento_responsable__isnull=True)
        node_name = "Sin Departamento"
        
    if falla_id:
        ticket_qs = ticket_qs.filter(Q(falla_reportada_id=falla_id) | Q(falla_reportada__parent_id=falla_id))
        try: node_name = FallaTicket.objects.get(id=falla_id).nombre
        except: pass
        
    if ubicacion_id:
        try:
            loc = Ubicacion.objects.get(id=ubicacion_id)
            desc_ids = loc.get_descendants(include_self=True).values_list('id', flat=True)
            ticket_qs = ticket_qs.filter(ubicacion_id__in=desc_ids)
            node_name = loc.nombre
        except: pass

    html = render_to_string('callcenter/partials/node_ticket_list.html', {
        'tickets': ticket_qs.order_by('-fecha_solicitud')[:100],
        'node_name': node_name
    }, request=request)
    
    return JsonResponse({'html': html})

@staff_member_required
@require_POST
def update_ticket_deductiva_ajax(request, ticket_id):
    """
    Actualiza la deductiva de un ticket específico vía AJAX y retorna los totales actualizados del cluster.
    """
    from decimal import Decimal
    from django.db.models import Sum
    import json
    
    ticket = get_object_or_404(SolicitudTicket, id=ticket_id)
    
    # Soporte para JSON body o POST tradicional
    deductiva_val = '0.00'
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            deductiva_val = str(data.get('deductiva', '0.00'))
        except:
            pass
    else:
        deductiva_val = request.POST.get('deductiva', '0.00')
        
    try:
        clean_val = deductiva_val.replace(',', '').strip()
        ticket.deductiva = Decimal(clean_val)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Monto inválido: {str(e)}'}, status=400)
        
    ticket.save()
    
    # Recalcular totales del cluster para retornar y actualizar cabecera en vivo
    cluster = ticket.grupo
    if cluster:
        all_tickets = cluster.tickets.all()
        total_ded = all_tickets.aggregate(total=Sum('deductiva'))['total'] or Decimal('0.00')
        total_ded_abiertos = all_tickets.filter(fecha_cierre__isnull=True, cierre_enviado=False).aggregate(total=Sum('deductiva'))['total'] or Decimal('0.00')
        total_ded_cerrados = all_tickets.filter(Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True)).aggregate(total=Sum('deductiva'))['total'] or Decimal('0.00')
    else:
        total_ded = Decimal('0.00')
        total_ded_abiertos = Decimal('0.00')
        total_ded_cerrados = Decimal('0.00')
        
    return JsonResponse({
        'success': True,
        'ticket_id': ticket_id,
        'deductiva': float(ticket.deductiva),
        'total_deductiva': float(total_ded),
        'total_deductiva_abiertos': float(total_ded_abiertos),
        'total_deductiva_cerrados': float(total_ded_cerrados),
    })


@staff_member_required
@require_POST
def import_deductivas_excel_ajax(request, cluster_id):
    """
    Importa deductivas desde un archivo Excel (.xlsx) que fue previamente exportado
    desde el dashboard del cluster. Busca la columna 'Deductiva (USD)' y el identificador
    'Folio/ID' para hacer match con los tickets del cluster.
    """
    from decimal import Decimal, InvalidOperation
    from django.db.models import Sum, Q
    from .models import GrupoTicket, SolicitudTicket
    import pandas as pd

    cluster_id = int(str(cluster_id).replace(',', ''))
    cluster = get_object_or_404(GrupoTicket, id=cluster_id)

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'success': False, 'error': 'No se recibió ningún archivo.'}, status=400)

    if not file.name.endswith('.xlsx'):
        return JsonResponse({'success': False, 'error': 'El archivo debe ser formato .xlsx'}, status=400)

    try:
        df = pd.read_excel(file)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'No se pudo leer el archivo Excel: {str(e)}'}, status=400)

    # Buscar columnas necesarias (case-insensitive, strip whitespace)
    col_map = {c.strip().lower(): c for c in df.columns}

    folio_col = None
    deductiva_col = None

    for key, original in col_map.items():
        if key in ('folio/id', 'folio / id', 'folio', 'folio_id'):
            folio_col = original
        if key in ('deductiva (usd)', 'deductiva(usd)', 'deductiva'):
            deductiva_col = original

    if not folio_col:
        return JsonResponse({
            'success': False,
            'error': f'No se encontró la columna "Folio/ID" en el Excel. Columnas encontradas: {", ".join(df.columns.tolist())}'
        }, status=400)

    if not deductiva_col:
        return JsonResponse({
            'success': False,
            'error': f'No se encontró la columna "Deductiva (USD)" en el Excel. Columnas encontradas: {", ".join(df.columns.tolist())}'
        }, status=400)

    # Pre-cargar todos los tickets del cluster en un dict para búsqueda O(1)
    all_tickets = cluster.tickets.all()
    tickets_by_folio = {}
    tickets_by_id = {}
    for t in all_tickets:
        if t.folio:
            clean_f = str(t.folio).replace(' ', '').lower()
            tickets_by_folio[clean_f] = t
        tickets_by_id[str(t.id_solicitud)] = t

    updated = 0
    skipped = 0
    errors = 0
    agregados_al_cluster = 0
    details = []

    for idx, row in df.iterrows():
        folio_val = str(row[folio_col]).strip() if pd.notna(row[folio_col]) else ''
        deductiva_val = row[deductiva_col]

        if not folio_val or folio_val.lower() == 'nan':
            continue

        clean_folio = folio_val.replace(' ', '').lower()
        
        # Buscar ticket por folio o por id_solicitud en el cluster actual
        ticket = tickets_by_folio.get(clean_folio) or tickets_by_id.get(clean_folio)
        
        # Fallback para casos en los que pandas lee el ID como float (ej: '145685.0')
        if not ticket and clean_folio.endswith('.0'):
            ticket = tickets_by_id.get(clean_folio[:-2])

        # Si no está en el cluster, buscar globalmente y agregarlo
        if not ticket:
            global_ticket = None
            try:
                clean_folio_no_decimals = folio_val.replace('.0', '')
                
                # Crear los filtros. Siempre buscamos en folio exacto primero
                q_filter = Q(folio__iexact=folio_val) | Q(folio__iexact=clean_folio_no_decimals)
                
                # Solo buscamos en id_solicitud si el valor es numérico
                if folio_val.isdigit():
                    q_filter |= Q(id_solicitud=int(folio_val))
                elif clean_folio_no_decimals.isdigit():
                    q_filter |= Q(id_solicitud=int(clean_folio_no_decimals))
                    
                global_ticket = SolicitudTicket.objects.filter(q_filter).first()

                # BÚSQUEDA A PRUEBA DE BALAS: Si no lo encontró, y tiene un guión, buscar la parte numérica
                # (Esto resuelve los casos donde en la DB se guardó como 'SS26- 144975' con espacios)
                if not global_ticket and '-' in folio_val:
                    number_part = folio_val.split('-')[-1].replace('.0', '').strip()
                    if number_part.isdigit():
                        possible_tickets = SolicitudTicket.objects.filter(folio__icontains=number_part)
                        for pt in possible_tickets:
                            if pt.folio and str(pt.folio).replace(' ', '').lower() == clean_folio:
                                global_ticket = pt
                                break
                                
            except Exception as e:
                print(f"Error buscando ticket {folio_val}: {e}")
                pass
            
            if global_ticket:
                # Añadir el ticket global al cluster
                cluster.tickets.add(global_ticket)
                ticket = global_ticket
                agregados_al_cluster += 1
                
                # Actualizar los diccionarios locales por si hay duplicados en el excel
                if ticket.folio:
                    tickets_by_folio[str(ticket.folio).replace(' ', '').lower()] = ticket
                tickets_by_id[str(ticket.id_solicitud)] = ticket

        if not ticket:
            errors += 1
            details.append({
                'folio': folio_val,
                'deductiva': 0,
                'status': 'error',
                'msg': 'No existe en la base de datos'
            })
            continue

        try:
            if pd.isna(deductiva_val):
                new_deductiva = Decimal('0.00')
            else:
                clean_val = str(deductiva_val).replace(',', '').replace('$', '').strip()
                new_deductiva = Decimal(clean_val)
        except (InvalidOperation, ValueError):
            errors += 1
            details.append({
                'folio': folio_val,
                'deductiva': 0,
                'status': 'error',
                'msg': f'Valor inválido: {deductiva_val}'
            })
            continue

        current_deductiva = ticket.deductiva or Decimal('0.00')
        if current_deductiva == new_deductiva:
            skipped += 1
            details.append({
                'folio': folio_val,
                'deductiva': float(new_deductiva),
                'status': 'sin_cambio'
            })
        else:
            ticket.deductiva = new_deductiva
            ticket.save(update_fields=['deductiva'])
            updated += 1
            details.append({
                'folio': folio_val,
                'deductiva': float(new_deductiva),
                'status': 'actualizado'
            })

    # Recalcular totales del cluster
    total_ded = all_tickets.aggregate(total=Sum('deductiva'))['total'] or Decimal('0.00')
    total_ded_abiertos = all_tickets.exclude(
        Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True)
    ).aggregate(total=Sum('deductiva'))['total'] or Decimal('0.00')
    total_ded_cerrados = all_tickets.filter(
        Q(fecha_cierre__isnull=False) | Q(cierre_enviado=True)
    ).aggregate(total=Sum('deductiva'))['total'] or Decimal('0.00')

    return JsonResponse({
        'success': True,
        'updated': updated,
        'skipped': skipped,
        'errors': errors,
        'agregados': agregados_al_cluster,
        'total_rows': len(df),
        'details': details,
        'total_deductiva': float(total_ded),
        'total_deductiva_abiertos': float(total_ded_abiertos),
        'total_deductiva_cerrados': float(total_ded_cerrados),
    })

@staff_member_required
def download_deductivas_template(request):
    """
    Descarga una plantilla vacía de Excel para la importación de deductivas.
    """
    import pandas as pd
    from django.http import HttpResponse
    import io

    df = pd.DataFrame(columns=['Folio/ID', 'Deductiva (USD)'])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
        # Ajustar el ancho de las columnas
        worksheet = writer.sheets['Plantilla']
        worksheet.column_dimensions['A'].width = 20
        worksheet.column_dimensions['B'].width = 25

    output.seek(0)
    response = HttpResponse(
        output.read(), 
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="plantilla_importacion_deductivas.xlsx"'
    return response

@staff_member_required
def create_cluster_manual_ajax(request):
    """
    Crea un cluster manualmente sin wizard.
    POST: correlativo, descripcion, departamento_id
    """
    from django.urls import reverse

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Solo POST permitido'})
    
    correlativo = request.POST.get('correlativo', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    depto_id = request.POST.get('departamento_id')
    
    if not correlativo:
        return JsonResponse({'success': False, 'error': 'El nombre del cluster es obligatorio.'})
    if not depto_id:
        return JsonResponse({'success': False, 'error': 'El departamento es obligatorio.'})
    
    from django.contrib.auth.models import User
    from core.models import Departamento
    
    try:
        depto = Departamento.objects.get(id=depto_id)
    except Departamento.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Departamento no encontrado.'})
    
    # Asegurar unicidad del correlativo
    base_correlativo = correlativo
    counter = 1
    while GrupoTicket.objects.filter(correlativo=correlativo).exists():
        correlativo = f"{base_correlativo} ({counter})"
        counter += 1
    
    cluster = GrupoTicket.objects.create(
        correlativo=correlativo,
        descripcion=descripcion or f"Cluster manual - {correlativo}",
        departamento=depto,
        usuario_creador=request.user if request.user.is_authenticated else None,
    )
    
    return JsonResponse({
        'success': True,
        'cluster_id': cluster.id,
        'correlativo': cluster.correlativo,
        'redirect_url': reverse('callcenter:cluster_tickets', args=[cluster.id])
    })
