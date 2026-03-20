import base64
import logging
import os
from datetime import datetime

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from playwright.sync_api import sync_playwright

from ..models import PermisoTrabajo

logger = logging.getLogger(__name__)

@staff_member_required
def generar_permiso_pdf_view(request, permiso_id):
    """
    Genera un reporte PDF del Permiso de Trabajo con formato premium.
    """
    permiso = get_object_or_404(
        PermisoTrabajo.objects.select_related(
            'tipo', 'ubicacion', 'orden_trabajo', 'solicitante', 'autorizado_por'
        ).prefetch_related('verificaciones__requisito'), 
        pk=permiso_id
    )

    # Logo en Base64
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo_dcc.png')
    logo_dcc_b64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as image_file:
            logo_dcc_b64 = base64.b64encode(image_file.read()).decode('utf-8')

    context = {
        'permiso': permiso,
        'verificaciones': permiso.verificaciones.all(),
        'logo_dcc_b64': logo_dcc_b64,
        'ahora': timezone.now(),
    }

    html_content = render_to_string('seguridad/permiso_pdf.html', context)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content)
        
        # Generar PDF
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "0cm", "bottom": "0cm", "left": "0cm", "right": "0cm"}
        )
        browser.close()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"Permiso_{permiso.tipo.nombre.replace(' ', '_')}_{permiso.id}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    
    return response

# Helper for get_object_or_404 (imported locally if not at top)
from django.shortcuts import get_object_or_404
