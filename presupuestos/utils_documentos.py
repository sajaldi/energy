import os
import io
import logging
import tempfile
import base64
import qrcode
from datetime import datetime
from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

def render_requisicion_pdf(requisicion):
    """
    Renderiza el HTML de la requisición y lo convierte a PDF (bytes) usando Playwright.
    """
    try:
        # 1. Preparar datos para la plantilla
        solicitante = requisicion.usuario_solicitante
        perfil_sol = getattr(solicitante, 'perfil', None) if solicitante else None
        
        # Cargar logo en base64
        logo_base64 = ""
        logo_path = os.path.join(settings.BASE_DIR, 'plantilla_files', 'image001.png')
        if os.path.exists(logo_path):
            try:
                with open(logo_path, "rb") as f:
                    logo_base64 = base64.b64encode(f.read()).decode('utf-8')
            except Exception as e:
                logger.warning(f"No se pudo cargar el logo para el PDF: {e}")

        # Generar QR en base64
        qr_base64 = ""
        try:
            # URL de validación o acceso al PDF
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            target_url = f"{site_url}/presupuestos/requisiciones/{requisicion.pk}/pdf/"
            
            qr = qrcode.QRCode(version=1, box_size=10, border=0)
            qr.add_data(target_url)
            qr.make(fit=True)
            img_qr = qr.make_image(fill_color="black", back_color="white")
            
            buffered = io.BytesIO()
            img_qr.save(buffered, format="PNG")
            qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Exception as e:
            logger.warning(f"Error generando QR para el PDF: {e}")

        # Obtener artículos
        articulos_data = []
        for i, art in enumerate(requisicion.articulos.all(), 1):
            articulos_data.append({
                'idx': i,
                'descripcion': art.cr8ca_articulo,
                'cantidad': float(art.cr8ca_cantidad or 0),
                'precio': float(art.cr8ca_costoaproximado or 0),
                'subtotal': float(art.subtotal or 0),
                'unidad': 'UND' 
            })

        # Extraer comentarios de aprobación
        comentarios_aprov = requisicion.cr8ca_comentarios or ""

        context = {
            'LOGO_BASE64': logo_base64,
            'QR_BASE64': qr_base64,
            'EMPRESA_NOMBRE': "OPERADORA DE INFRAESTRUCTURA DE HONDURAS S.A. DE C.V",
            'PROYECTO_NOMBRE': "Centro Cívico Gubernamental Honduras",
            'CODIGO_FORMATO': "OCC-PYS-FOR-02",
            'ESTADO_TEXTO': "Aprobado" if requisicion.estado_requisicion == 'AUTORIZADO' else (requisicion.get_estado_requisicion_display() if hasattr(requisicion, 'get_estado_requisicion_display') else "En Revisión"),
            'FECHA_CABECERA': datetime.now().strftime('%d/%m/%Y'),
            
            'NUMERO': requisicion.cr8ca_requisicion,
            'ASUNTO': getattr(requisicion, 'cr8ca_asunto', 'N/A'),
            'FECHA': requisicion.fecha.strftime('%d/%m/%Y %H:%M') if requisicion.fecha else '',
            'SOLICITANTE': f"{solicitante.first_name} {solicitante.last_name}".strip() if (solicitante and (solicitante.first_name or solicitante.last_name)) else (solicitante.username if solicitante else 'N/A'),
            'DEPARTAMENTO': perfil_sol.departamento.nombre if perfil_sol and perfil_sol.departamento else 'N/A',
            'MOTIVO': requisicion.cr8ca_motivo,
            'TOTAL': float(requisicion.total_estimado),
            'ARTICULOS': articulos_data,
            'COMENTARIOS_APROBACION': comentarios_aprov,
            'FECHA_GENERACION': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'FECHA_ISO': datetime.now().strftime('%Y%m%d%H%M'),
            'APROBADOR_NOMBRE': perfil_sol.responsable.get_full_name() if (perfil_sol and perfil_sol.responsable) else "Gerencia"
        }

        # 2. Renderizar HTML a string
        html_content = render_to_string('pdf/requisicion_print.html', context)

        # 3. Convertir HTML a PDF usando Playwright
        pdf_content = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_content(html_content)
                
                pdf_content = page.pdf(
                    format="Letter",
                    print_background=True,
                    margin={"top": "20px", "right": "20px", "bottom": "20px", "left": "20px"}
                )
                browser.close()
            return pdf_content
        except Exception as pw_err:
            logger.error(f"Error crítico en Playwright: {pw_err}")
            raise pw_err

    except Exception as e:
        logger.exception(f"Error inesperado renderizando PDF: {e}")
        return None

def generate_requisicion_pdf(requisicion):
    """
    Genera el PDF y lo guarda en MinIO vinculado a la requisición.
    """
    pdf_content = render_requisicion_pdf(requisicion)
    if not pdf_content:
        return None
        
    try:
        from .models import DocumentoRequisicion
        file_name = f"Requisicion_{requisicion.cr8ca_requisicion}.pdf"
        
        doc_obj = DocumentoRequisicion(
            requisicion=requisicion,
            nombre=f"Requisición Oficial - {requisicion.cr8ca_requisicion}"
        )
        doc_obj.archivo.save(file_name, ContentFile(pdf_content))
        doc_obj.save()
        
        logger.info(f"PDF generado y guardado exitosamente para {requisicion.cr8ca_requisicion}")
        return doc_obj
    except Exception as e:
        logger.exception(f"Error guardando PDF en MinIO: {e}")
        return None
