import os
import io
import logging
import tempfile
from datetime import datetime
from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

def generate_requisicion_pdf(requisicion):
    """
    Renderiza un HTML basado en la requisición y lo convierte a PDF usando Playwright.
    Luego guarda el resultado en el storage (MinIO).
    """
    try:
        # 1. Preparar datos para la plantilla
        solicitante = requisicion.usuario_solicitante
        perfil_sol = getattr(solicitante, 'perfil', None) if solicitante else None
        
        # Obtener artículos
        articulos_data = []
        for i, art in enumerate(requisicion.articulos.all(), 1):
            articulos_data.append({
                'idx': i,
                'descripcion': art.cr8ca_articulo,
                'cantidad': float(art.cr8ca_cantidad),
                'precio': float(art.cr8ca_costoaproximado or 0),
                'subtotal': float(art.subtotal)
            })

        # Extraer comentarios de aprobación del historial si existen
        comentarios_aprov = ""
        if requisicion.cr8ca_comentarios:
            # Intentar sacar el último comentario de Power Automate
            lines = requisicion.cr8ca_comentarios.split('\n')
            for line in reversed(lines):
                if "Power Automate" in line:
                    comentarios_aprov = line
                    break

        context = {
            'NUMERO': requisicion.cr8ca_requisicion,
            'ASUNTO': requisicion.cr8ca_asunto,
            'FECHA': requisicion.fecha.strftime('%d/%m/%Y %H:%M') if requisicion.fecha else '',
            'SOLICITANTE': f"{solicitante.first_name} {solicitante.last_name}".strip() if (solicitante and (solicitante.first_name or solicitante.last_name)) else (solicitante.username if solicitante else 'N/A'),
            'DEPARTAMENTO': perfil_sol.departamento.nombre if perfil_sol and perfil_sol.departamento else 'N/A',
            'MOTIVO': requisicion.cr8ca_motivo,
            'TOTAL': float(requisicion.total_estimado),
            'ARTICULOS': articulos_data,
            'PROVEEDORES': ", ".join([p.nombre for p in requisicion.proveedores_sugeridos.all()]) or (requisicion.proveedor.nombre if requisicion.proveedor else 'N/A'),
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
                # Usamos chromium en modo headless
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Seteamos el contenido HTML
                page.set_content(html_content)
                
                # Esperamos un momento para que los estilos carguen si fuera necesario
                # (en este caso es CSS inline o en <style>, así que es instantáneo)
                
                # Generamos el PDF
                pdf_content = page.pdf(
                    format="Letter",
                    print_background=True,
                    margin={"top": "0px", "right": "0px", "bottom": "0px", "left": "0px"}
                )
                
                browser.close()
        except Exception as pw_err:
            logger.error(f"Error crítico en Playwright: {str(pw_err)}")
            # Si falla Playwright (ej. no están los binarios del browser), lanzamos para el fallback
            raise pw_err

        # 4. Guardar en MinIO vinculado a la requisición
        if pdf_content:
            from .models import DocumentoRequisicion
            
            file_name = f"Requisicion_{requisicion.cr8ca_requisicion}.pdf"
            
            # Borrar documentos previos que tengan el mismo nombre "Final" para no duplicar
            # Requisicion.documentos.filter(nombre__icontains="Final").delete()
            
            doc_obj = DocumentoRequisicion(
                requisicion=requisicion,
                nombre=f"Documento de Requisición Oficial - {requisicion.cr8ca_requisicion}"
            )
            doc_obj.archivo.save(file_name, ContentFile(pdf_content))
            doc_obj.save()
            
            logger.info(f"PDF generado y guardado exitosamente para {requisicion.cr8ca_requisicion}")
            return doc_obj

    except Exception as e:
        logger.exception(f"Error inesperado generando PDF: {str(e)}")
        return None
