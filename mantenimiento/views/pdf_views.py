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

from ..models import OrdenTrabajo, ValorPasoOrden

logger = logging.getLogger(__name__)

@staff_member_required
def generate_rutina_pdf_view(request, ot_id):
    try:
        ot = OrdenTrabajo.objects.select_related('rutina', 'rutina__frecuencia', 'rutina__tipo', 'ubicacion', 'tecnico', 'cierre').get(pk=ot_id)
    except OrdenTrabajo.DoesNotExist:
        raise Http404("Orden de Trabajo no encontrada")

    # Fetch checklist results
    results = ValorPasoOrden.objects.filter(orden_trabajo=ot).select_related('paso').order_by('paso__orden')
    
    # Pre-process data for the template
    empresa_nombre = "Operadora de Infraestructura de Honduras, S.A. de C.V."
    supervisor_nombre = "Allan Castellanos" # Default per user design
    
    # Get edificio root or first building parent
    edificio = ot.ubicacion.get_root() if ot.ubicacion else None
    edificio_nombre = edificio.nombre if edificio else "N/A"
    
    activo_nombre = ot.activos.first().nombre if ot.activos.exists() else "N/A"

    # Encode logo
    logo_dcc_b64 = ""
    logo_path = os.path.join(settings.BASE_DIR, 'activos', 'static', 'activos', 'img', 'logo_operadora_cc.png')
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as bf:
            logo_dcc_b64 = base64.b64encode(bf.read()).decode('utf-8')

    context = {
        'ot': ot,
        'checklist_items': results,
        'empresa_nombre': empresa_nombre,
        'supervisor_nombre': supervisor_nombre,
        'edificio_nombre': edificio_nombre,
        'activo_nombre': activo_nombre,
        'logo_dcc_b64': logo_dcc_b64,
        'ahora': timezone.now(),
    }

    html_content = render_to_string('mantenimiento/rutina_pdf.html', context, request=request)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            page.set_content(html_content, wait_until='networkidle')
            # Adjust scale to fit more content if needed
            pdf_bytes = page.pdf(format="A4", print_background=True, margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'})
            browser.close()

        file_name = f'rutina_{ot.codigo_de_orden or ot.id}_{uuid.uuid4().hex[:6]}.pdf'
        
        # We could save this to a new model or just return it. 
        # For now, let's return it as a direct download or preview.
        from django.http import HttpResponse
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{file_name}"'
        return response

    except Exception as e:
        logger.error(f"Error generating Routine PDF: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
