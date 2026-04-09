import base64
import json
import logging
import os
import uuid
from datetime import datetime

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.base import ContentFile
from django.http import JsonResponse, Http404
from django.template.loader import render_to_string
from django.utils import timezone
from playwright.sync_api import sync_playwright

from ..models import OrdenTrabajo, ValorPasoOrden, ArchivoOrdenTrabajo, Aviso

logger = logging.getLogger(__name__)

@staff_member_required
def generate_rutina_pdf_view(request, ot_id):
    from ..utils.pdf_utils import generate_ot_pdf_bytes
    from django.http import HttpResponse, Http404, JsonResponse

    try:
        ot = OrdenTrabajo.objects.get(pk=ot_id)
    except OrdenTrabajo.DoesNotExist:
        raise Http404("Orden de Trabajo no encontrada")

    # 1. Intentar servir el archivo adjunto si ya existe (Cache/Background result)
    filename = f"OT_{ot.id}.pdf"
    archivo_adjunto = ArchivoOrdenTrabajo.objects.filter(orden_trabajo=ot, nombre=filename).first()
    
    if archivo_adjunto:
        try:
            # Si el archivo está en MinIO/S3, redirigir o servir el contenido
            # Por simplicidad y consistencia, redirigimos a la URL firmada
            from django.shortcuts import redirect
            return redirect(archivo_adjunto.archivo.url)
        except Exception as e:
            logger.warning(f"Error sirviendo adjunto existente para OT {ot.id}: {e}")

    # 2. Si no existe o falló, generar en caliente (síncrono)
    try:
        pdf_bytes = generate_ot_pdf_bytes(ot, request=request)
        file_name = f'Reporte_OT_{ot.id}.pdf'
        
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{file_name}"'
        return response

    except Exception as e:
        logger.error(f"Error generating Routine PDF: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@staff_member_required
def generate_aviso_pdf_view(request, aviso_id):
    try:
        aviso = Aviso.objects.select_related('solicitante', 'ubicacion', 'activo', 'falla').get(pk=aviso_id)
    except Aviso.DoesNotExist:
        raise Http404("Aviso no encontrado")

    empresa_nombre = "Operadora de Infraestructura de Honduras, S.A. de C.V."
    
    # Get edificio root or first building parent
    edificio = aviso.ubicacion.get_root() if aviso.ubicacion else (aviso.activo.ubicacion.get_root() if aviso.activo and aviso.activo.ubicacion else None)
    edificio_nombre = edificio.nombre if edificio else "N/A"
    
    # Encode logo
    logo_dcc_b64 = ""
    logo_path = os.path.join(settings.BASE_DIR, 'activos', 'static', 'activos', 'img', 'logo_operadora_cc.png')
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as bf:
            logo_dcc_b64 = base64.b64encode(bf.read()).decode('utf-8')

    # Fetch image attachments for the PDF
    fotos_adjuntas = []
    has_fotos = False
    
    # Add extra photos from FotoAviso model
    for archivo in aviso.fotos.all().order_by('creado_en'):
        has_fotos = True
        try:
            if archivo.foto:
                img_data = archivo.foto.read()
                ext = os.path.splitext(archivo.foto.name)[1].lower().replace('.', '')
                mime = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif', 'webp': 'webp'}.get(ext, 'jpeg')
                b64 = base64.b64encode(img_data).decode('utf-8')
                fotos_adjuntas.append({
                    'nombre': 'Evidencia Visual',
                    'data_uri': f'data:image/{mime};base64,{b64}',
                    'creado_en': archivo.creado_en,
                    'descripcion': archivo.descripcion or '',
                })
        except Exception as e:
            logger.warning(f"Could not read attachment {archivo.id}: {e}")

    # Add main photo if exists and no extra photos are attached
    if not has_fotos and aviso.foto:
        try:
            img_data = aviso.foto.read()
            ext = os.path.splitext(aviso.foto.name)[1].lower().replace('.', '')
            mime = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif', 'webp': 'webp'}.get(ext, 'jpeg')
            b64 = base64.b64encode(img_data).decode('utf-8')
            fotos_adjuntas.append({
                'nombre': 'Foto Principal',
                'data_uri': f'data:image/{mime};base64,{b64}',
                'creado_en': aviso.creado_en,
            })
        except Exception as e:
            logger.warning(f"Could not read main photo for Aviso {aviso.id}: {e}")

    context = {
        'aviso': aviso,
        'empresa_nombre': empresa_nombre,
        'edificio_nombre': edificio_nombre,
        'logo_dcc_b64': logo_dcc_b64,
        'fotos_adjuntas': fotos_adjuntas,
        'ahora': timezone.now(),
    }

    html_content = render_to_string('mantenimiento/aviso_pdf.html', context, request=request)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            page.set_content(html_content, wait_until='networkidle')
            pdf_bytes = page.pdf(format="A4", print_background=True, margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'})
            browser.close()

        file_name = f'aviso_{aviso.id}_{uuid.uuid4().hex[:6]}.pdf'
        
        from django.http import HttpResponse
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{file_name}"'
        return response

    except Exception as e:
        logger.error(f"Error generating Aviso PDF: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

