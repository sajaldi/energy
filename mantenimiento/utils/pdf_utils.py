import base64
import logging
import os
import uuid
from datetime import datetime
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from playwright.sync_api import sync_playwright
from PIL import Image
import io

logger = logging.getLogger(__name__)

def _optimize_image(img_data, max_width=800, quality=75):
    """
    Resizes and compresses images to speed up PDF generation.
    """
    try:
        img = Image.open(io.BytesIO(img_data))
        
        # Convert to RGB if necessary (Alpha channel can be problematic in some PDF engines)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # Resize if too large
        if img.width > max_width:
            new_height = int(img.height * (max_width / img.width))
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.warning(f"Error optimizing image: {e}")
        return img_data # Fallback to original

def generate_ot_pdf_bytes(ot, request=None, pdf_url=None):
    """
    Generates PDF bytes for a Work Order using Playwright.
    Logic extracted from generate_rutina_pdf_view.
    """
    from ..models import ValorPasoOrden, ArchivoOrdenTrabajo
    
    # Pre-process data for the template
    pasos = ot.rutina.pasos.all().order_by('orden') if ot.rutina else []
    results_qs = ValorPasoOrden.objects.filter(orden_trabajo=ot).select_related('paso')
    results_dict = {r.paso_id: r for r in results_qs}
    
    checklist_items = []
    for paso in pasos:
        item = results_dict.get(paso.id)
        if item:
            checklist_items.append(item)
        else:
            checklist_items.append({
                'paso': paso,
                'valor_bool': None,
                'valor_numerico': None,
                'no_aplica': False,
                'comentarios': ''
            })
    
    empresa_nombre = "Operadora de Infraestructura de Honduras, S.A. de C.V."
    supervisor_nombre = "Allan Castellanos"
    if ot.supervisor:
        supervisor_nombre = ot.supervisor.get_full_name()
    elif ot.tecnico:
        supervisor_nombre = ot.tecnico.get_full_name()
    
    edificio = ot.ubicacion.get_root() if ot.ubicacion else None
    edificio_nombre = edificio.nombre if edificio else "N/A"
    ubicacion_completa = ot.ubicacion.get_ruta_completa() if ot.ubicacion else "N/A"
    activo_obj = ot.activos.first()
    activo_nombre = "N/A"
    if activo_obj:
        activo_nombre = activo_obj.nombre
        if activo_obj.descripcion:
            activo_nombre += f" - {activo_obj.descripcion}"
    
    # Datos del Técnico Líder (Prioridad: tecnico_puesto > tecnico user)
    tecnico_perfil = None
    if ot.tecnico_puesto:
        tecnico_perfil = ot.tecnico_puesto
    elif ot.tecnico and hasattr(ot.tecnico, 'perfil_tecnico'):
        tecnico_perfil = ot.tecnico.perfil_tecnico

    # Empresa Responsable (Prioridad: Campo Directo > Empresa del Perfil > Default)
    empresa_nombre = "Operadora de Infraestructura de Honduras, S.A. de C.V."
    if ot.empresa_responsable:
        empresa_nombre = ot.empresa_responsable.nombre
    elif tecnico_perfil and tecnico_perfil.empresa:
        empresa_nombre = tecnico_perfil.empresa.nombre
    
    # Técnicos (Lista consolidada y estructurada: Líder + Equipo)
    tecnicos_data = []
    seen_personnel_ids = set()

    # 1. Agregar Líder
    if tecnico_perfil:
        t_nombre = f"{tecnico_perfil.nombre} {tecnico_perfil.apellido}" if not tecnico_perfil.user else (tecnico_perfil.user.get_full_name() or tecnico_perfil.user.username)
        t_dni = tecnico_perfil.dni or "N/A"
        tecnicos_data.append({'nombre': t_nombre, 'dni': t_dni, 'es_lider': True})
        seen_personnel_ids.add(f"p_{tecnico_perfil.id}")

    # 2. Agregar Colaboradores (Personal/TecnicoPuesto)
    for p in ot.colaboradores_puesto.all():
        p_key = f"p_{p.id}"
        if p_key not in seen_personnel_ids:
            p_nombre = f"{p.nombre} {p.apellido}" if not p.user else (p.user.get_full_name() or p.user.username)
            tecnicos_data.append({'nombre': p_nombre, 'dni': p.dni or "N/A", 'es_lider': False})
            seen_personnel_ids.add(p_key)

    # 3. Agregar Colaboradores (Usuarios legacy)
    for u in ot.tecnicos.all():
        u_perfil = getattr(u, 'perfil_tecnico', None)
        u_key = f"p_{u_perfil.id}" if u_perfil else f"u_{u.id}"
        if u_key not in seen_personnel_ids:
            tecnicos_data.append({
                'nombre': u.get_full_name() or u.username, 
                'dni': u_perfil.dni if u_perfil else "N/A",
                'es_lider': False
            })
            seen_personnel_ids.add(u_key)

    # Variables para compatibilidad con templates viejos
    tecnico_nombre = tecnicos_data[0]['nombre'] if tecnicos_data else "N/A"
    tecnico_dni = tecnicos_data[0]['dni'] if tecnicos_data else "N/A"

    # Generar QR de Firma para OTNP (Apunta a la URL del PDF)
    signature_qr_b64 = ""
    if ot.tipo == 'NO_PROGRAMADA':
        import qrcode
        from io import BytesIO
        
        # Usar la URL proporcionada o construir una por defecto
        final_pdf_url = pdf_url
        if not final_pdf_url:
            final_pdf_url = f"{settings.SITE_URL}/mantenimiento/app/ot/{ot.id}/pdf/"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=1)
        qr.add_data(final_pdf_url)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img_qr.save(buffer, format="PNG")
        signature_qr_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    # Encode logo
    logo_dcc_b64 = ""
    logo_path = os.path.join(settings.BASE_DIR, 'activos', 'static', 'activos', 'img', 'logo_operadora_cc.png')
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as bf:
            logo_dcc_b64 = base64.b64encode(bf.read()).decode('utf-8')

    # Fetch image attachments
    fotos_adjuntas = []
    archivos_img = ArchivoOrdenTrabajo.objects.filter(orden_trabajo=ot, tipo='IMAGEN').select_related('paso').order_by('creado_en')
    vpo_dict = {item.paso_id: item for item in results_qs}
    
    for archivo in archivos_img:
        try:
            img_data = archivo.archivo.read()
            ext = os.path.splitext(archivo.archivo.name)[1].lower().replace('.', '')
            mime = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif', 'webp': 'webp'}.get(ext, 'jpeg')
            # Optimize image for PDF (reduce size)
            optimized_data = _optimize_image(img_data)
            b64 = base64.b64encode(optimized_data).decode('utf-8')
            
            nombre = archivo.nombre or 'Evidencia Fotográfica'
            descripcion = ''
            
            if archivo.paso:
                nombre = archivo.paso.descripcion
                vpo = vpo_dict.get(archivo.paso_id)
                if vpo and vpo.comentarios:
                    descripcion = vpo.comentarios

            fotos_adjuntas.append({
                'nombre': nombre,
                'descripcion': descripcion,
                'data_uri': f'data:image/{mime};base64,{b64}',
                'creado_en': archivo.creado_en,
            })
        except Exception as e:
            logger.warning(f"Could not read attachment {archivo.id}: {e}")

    context = {
        'ot': ot,
        'checklist_items': checklist_items,
        'empresa_nombre': empresa_nombre,
        'tecnico_nombre': tecnico_nombre,
        'tecnico_dni': tecnico_dni,
        'tecnicos_data': tecnicos_data,
        'supervisor_nombre': supervisor_nombre,
        'edificio_nombre': edificio_nombre,
        'ubicacion_completa': ubicacion_completa,
        'activo_nombre': activo_nombre,
        'logo_dcc_b64': logo_dcc_b64,
        'signature_qr_b64': signature_qr_b64,
        'fotos_adjuntas': fotos_adjuntas,
        'inicio_programado': ot.inicio_programado,
        'fin_programado': ot.fin_programado,
        'ahora': timezone.now(),
    }

    html_content = render_to_string('mantenimiento/rutina_pdf.html', context, request=request)

    # Use more optimized browser flags
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, 
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--single-process'
            ]
        )
        page = browser.new_page()
        page.set_content(html_content, wait_until='load')
        pdf_bytes = page.pdf(
            format="A4", 
            print_background=True, 
            margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'}
        )
        browser.close()
    
    return pdf_bytes
