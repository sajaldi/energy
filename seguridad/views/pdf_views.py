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

from ..models import PermisoTrabajo, LevantamientoConfiscacion

logger = logging.getLogger(__name__)

def render_to_pdf(template_src, context_dict={}):
    """
    Helper para renderizar un template HTML a PDF usando Playwright.
    """
    html_content = render_to_string(template_src, context_dict)
    
    with sync_playwright() as p:
        # Usar --no-sandbox para compatibilidad en entornos server/docker
        browser = p.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page()
        page.set_content(html_content)
        
        # Esperar a que las imágenes carguen si es necesario
        page.wait_for_load_state('networkidle')
        
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"}
        )
        browser.close()
        return pdf_bytes

@staff_member_required
def generar_permiso_pdf_view(request, permiso_id):
    """
    Genera un reporte PDF del Permiso de Trabajo con formato premium.
    """
    from django.shortcuts import get_object_or_404
    permiso = get_object_or_404(
        PermisoTrabajo.objects.select_related(
            'tipo', 'ubicacion', 'orden_trabajo', 'solicitante', 'autorizado_por'
        ).prefetch_related('verificaciones__requisito'), 
        pk=permiso_id
    )

    logo_path = os.path.join(settings.BASE_DIR, 'activos', 'static', 'activos', 'img', 'logo_operadora_cc.png')
    logo_dcc_b64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as image_file:
            logo_dcc_b64 = base64.b64encode(image_file.read()).decode('utf-8')

    # Filtrar y numerar requisitos dinámicamente
    verificaciones_raw = list(permiso.verificaciones.select_related('requisito').order_by('requisito__orden'))
    verificaciones_validas = []
    
    # Crear un mapa para búsqueda rápida por req_id
    mapa_verif = {v.requisito_id: v for v in verificaciones_raw}
    
    for v in verificaciones_raw:
        req = v.requisito
        mostrar = True
        
        if req.depende_de_id:
            parent_v = mapa_verif.get(req.depende_de_id)
            if parent_v:
                # Determinar el valor del padre
                parent_val = None
                if parent_v.requisito.tipo_respuesta == 'CHECK':
                    parent_val = parent_v.valor_bool
                elif parent_v.requisito.tipo_respuesta == 'NUMERICO':
                    parent_val = parent_v.valor_numerico is not None
                elif parent_v.requisito.tipo_respuesta in ['TEXTO', 'TABLA', 'FECHAHORA']:
                    parent_val = bool(parent_v.valor_texto)
                
                cond = req.depende_condicion
                if cond == 'TRUE' and parent_val is not True: mostrar = False
                elif cond == 'FALSE' and parent_val is not False: mostrar = False
                elif cond == 'FILLED' and not parent_val: mostrar = False
                elif cond == 'EMPTY' and parent_val: mostrar = False
        
        if mostrar:
            verificaciones_validas.append(v)

    # Numeración lógica
    counter = 1
    for v in verificaciones_validas:
        if v.requisito.tipo_respuesta != 'HEADER':
            v.display_number = counter
            counter += 1
        else:
            v.display_number = None

    context = {
        'permiso': permiso,
        'verificaciones': verificaciones_validas,
        'logo_dcc_b64': logo_dcc_b64,
        'ahora': timezone.now(),
    }

    pdf = render_to_pdf('seguridad/permiso_pdf.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"Permiso_{permiso.tipo.nombre.replace(' ', '_')}_{permiso.id}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    return HttpResponse("Error generando PDF", status=500)


@staff_member_required
def mobile_confiscacion_pdf_view(request, pk):
    """
    Genera el reporte PDF de un levantamiento de objetos confiscados.
    """
    from django.shortcuts import get_object_or_404
    levantamiento = get_object_or_404(
        LevantamientoConfiscacion.objects.select_related('ubicacion', 'inspector')
        .prefetch_related('objetos__catalogo_objeto', 'objetos__fotos'),
        pk=pk
    )

    logo_path = os.path.join(settings.BASE_DIR, 'activos', 'static', 'activos', 'img', 'logo_operadora_cc.png')
    logo_dcc_b64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as image_file:
            logo_dcc_b64 = base64.b64encode(image_file.read()).decode('utf-8')

    # Adjuntar b64 directamente a las fotos para el PDF
    for obj in levantamiento.objetos.all():
        for foto in obj.fotos.all():
            try:
                with foto.foto.open('rb') as f:
                    foto.b64 = base64.b64encode(f.read()).decode('utf-8')
            except Exception as e:
                foto.b64 = None
                print(f"Error encoding photo {foto.id}: {e}")

    context = {
        'levantamiento': levantamiento,
        'objetos': levantamiento.objetos.all(),
        'logo_dcc_b64': logo_dcc_b64,
        'ahora': timezone.now(),
    }

    pdf = render_to_pdf('seguridad/confiscacion_reporte_pdf.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"Reporte_Confiscacion_{levantamiento.folio}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    return HttpResponse("Error generando PDF", status=500)
