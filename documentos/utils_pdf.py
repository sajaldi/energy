"""
Utilidades para generar PDFs con firmas estampadas
"""

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
import os
from django.conf import settings


def estampar_firmas_en_pdf(documento_firmado):
    """
    Genera un PDF con todas las firmas estampadas visualmente
    
    Args:
        documento_firmado: Instancia de DocumentoFirmado
        
    Returns:
        BytesIO: Buffer con el PDF firmado
    """
    
    # Obtener el PDF original
    if not documento_firmado.revision or not documento_firmado.revision.archivo:
        raise ValueError("El documento no tiene un archivo asociado")
    
    archivo_original = documento_firmado.revision.archivo.path
    
    # Leer el PDF original
    pdf_reader = PdfReader(archivo_original)
    pdf_writer = PdfWriter()
    
    # Obtener todas las firmas aplicadas
    firmas = documento_firmado.firmas.filter(firmado=True).select_related('firmante')
    
    if not firmas.exists():
        # Si no hay firmas, retornar el original
        with open(archivo_original, 'rb') as f:
            return BytesIO(f.read())
    
    # Procesar cada página
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)
        
        # Crear un canvas temporal para las firmas de esta página
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=(page_width, page_height))
        
        # Agregar firmas que corresponden a esta página (numeración 1-indexed)
        firmas_pagina = firmas.filter(pagina=page_num + 1)
        
        for firma in firmas_pagina:
            if firma.imagen_firma:
                try:
                    # Calcular posición y tamaño
                    x = (firma.posicion_x / 100) * page_width
                    y = page_height - ((firma.posicion_y / 100) * page_height)  # Invertir Y
                    
                    width = (firma.ancho / 100) * page_width
                    height = (firma.alto / 100) * page_height
                    
                    # Ajustar Y para que la imagen esté en la posición correcta
                    y = y - height
                    
                    # ===== NUEVO: Dibujar BADGE DE CERTIFICACIÓN =====
                    # Rectángulo de fondo para el badge (arriba de la firma)
                    badge_height = 35
                    badge_y = y - badge_height - 2
                    
                    # Fondo del badge (gradiente simulado con rectángulos)
                    c.setFillColorRGB(0.15, 0.3, 0.6)  # Azul oscuro
                    c.rect(x, badge_y, width, badge_height, fill=1, stroke=0)
                    
                    # Borde dorado del badge
                    c.setStrokeColorRGB(0.85, 0.65, 0.13)  # Dorado
                    c.setLineWidth(2)
                    c.rect(x, badge_y, width, badge_height, fill=0, stroke=1)
                    
                    # Texto del badge
                    c.setFillColorRGB(1, 1, 1)  # Blanco
                    c.setFont("Helvetica-Bold", 8)
                    badge_text = "✓ FIRMADO DIGITALMENTE"
                    c.drawCentredString(x + width/2, badge_y + badge_height - 12, badge_text)
                    
                    # Token de verificación (más pequeño)
                    c.setFont("Helvetica", 6)
                    token_short = str(firma.token_verificacion)[:16] + "..."
                    c.drawCentredString(x + width/2, badge_y + badge_height - 24, f"Token: {token_short}")
                    
                    # ===== FIN BADGE =====
                    
                    # Dibujar la imagen de la firma
                    img_path = firma.imagen_firma.path
                    c.drawImage(
                        img_path,
                        x, y,
                        width=width,
                        height=height,
                        mask='auto',  # Respeta transparencia
                        preserveAspectRatio=True
                    )
                    
                    # ===== INFORMACIÓN DEL FIRMANTE DEBAJO =====
                    info_y = y - 15
                    
                    # Fondo semi-transparente para la info
                    c.setFillColorRGB(0.95, 0.95, 0.95)
                    info_height = 40
                    c.rect(x, info_y - info_height, width, info_height, fill=1, stroke=0)
                    
                    # Borde
                    c.setStrokeColorRGB(0.7, 0.7, 0.7)
                    c.setLineWidth(0.5)
                    c.rect(x, info_y - info_height, width, info_height, fill=0, stroke=1)
                    
                    # Texto de información
                    c.setFillColorRGB(0, 0, 0)
                    c.setFont("Helvetica-Bold", 7)
                    texto_firmante = firma.firmante.get_full_name()
                    c.drawString(x + 2, info_y - 10, texto_firmante)
                    
                    c.setFont("Helvetica", 6)
                    texto_fecha = firma.fecha_firma.strftime('%d/%m/%Y %H:%M:%S')
                    c.drawString(x + 2, info_y - 20, f"Fecha: {texto_fecha}")
                    
                    # IP del firmante
                    if firma.ip_firmante:
                        c.drawString(x + 2, info_y - 30, f"IP: {firma.ip_firmante}")
                    
                    # ===== LINK CLICKEABLE AL TOKEN =====
                    # Crear URL de verificación
                    from django.conf import settings
                    # Asumir que el dominio es el configurado o usar localhost para desarrollo
                    base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
                    verify_url = f"{base_url}/firmas/verificar/{firma.token_verificacion}/"
                    
                    # Agregar link clickeable en el badge
                    c.linkURL(
                        verify_url,
                        (x, badge_y, x + width, badge_y + badge_height),
                        relative=0,
                        thickness=0
                    )
                    
                    # Agregar icono de link
                    c.setFont("Helvetica", 6)
                    c.setFillColorRGB(0.3, 0.8, 1)  # Azul claro
                    c.drawString(x + 2, badge_y + 3, "🔗 Clic para verificar")
                    
                except Exception as e:
                    print(f"Error al estampar firma: {e}")
                    continue
        
        c.save()
        
        # Mover al inicio del buffer
        packet.seek(0)
        
        # Leer el canvas como PDF
        firma_pdf = PdfReader(packet)
        
        # Superponer la página de firmas sobre la página original
        if len(firma_pdf.pages) > 0:
            page.merge_page(firma_pdf.pages[0])
        
        # Agregar página al PDF de salida
        pdf_writer.add_page(page)
    
    # Guardar el PDF resultante en un buffer
    output_buffer = BytesIO()
    pdf_writer.write(output_buffer)
    output_buffer.seek(0)
    
    return output_buffer


def generar_pdf_firmado(documento_firmado):
    """
    Genera y guarda el PDF firmado en el modelo DocumentoFirmado
    
    Args:
        documento_firmado: Instancia de DocumentoFirmado
        
    Returns:
        bool: True si se generó exitosamente
    """
    try:
        # Generar el PDF con firmas
        pdf_buffer = estampar_firmas_en_pdf(documento_firmado)
        
        # Guardar en el campo pdf_firmado
        filename = f"{documento_firmado.documento.codigo}_firmado.pdf"
        
        from django.core.files.base import ContentFile
        documento_firmado.pdf_firmado.save(
            filename,
            ContentFile(pdf_buffer.read()),
            save=True
        )
        
        return True
        
    except Exception as e:
        print(f"Error al generar PDF firmado: {e}")
        return False


def generar_certificado_pdf(firma):
    """
    Genera un certificado de autenticidad en PDF
    
    Args:
        firma: Instancia de Firma
        
    Returns:
        BytesIO: Buffer con el PDF del certificado
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Título
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, height - 100, "CERTIFICADO DE AUTENTICIDAD")
    
    # Subtítulo
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height - 130, "Firma Electrónica Certificada")
    
    # Línea separadora
    c.line(100, height - 150, width - 100, height - 150)
    
    # Información
    y = height - 200
    c.setFont("Helvetica-Bold", 12)
    
    info = [
        ("Documento:", firma.documento_firmado.documento.codigo),
        ("Título:", firma.documento_firmado.documento.titulo),
        ("Firmante:", firma.firmante.get_full_name()),
        ("Fecha de Firma:", firma.fecha_firma.strftime('%d/%m/%Y %H:%M:%S')),
        ("Hash de Documento:", firma.documento_firmado.hash_documento_original),
        ("Hash de Firma:", firma.hash_firma),
        ("Token de Verificación:", str(firma.token_verificacion)),
    ]
    
    for label, value in info:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(100, y, label)
        c.setFont("Helvetica", 10)
        
        # Dividir textos largos
        if len(value) > 60:
            c.drawString(100, y - 15, value[:60])
            c.drawString(100, y - 30, value[60:])
            y -= 60
        else:
            c.drawString(250, y, value)
            y -= 30
    
    # Imagen de la firma
    if firma.imagen_firma:
        try:
            y -= 50
            c.setFont("Helvetica-Bold", 10)
            c.drawString(100, y, "Firma:")
            
            img_path = firma.imagen_firma.path
            c.drawImage(img_path, 100, y - 100, width=200, height=80, preserveAspectRatio=True)
        except:
            pass
    
    # Pie de página
    c.setFont("Helvetica", 8)
    c.drawCentredString(
        width/2, 50,
        f"Este certificado garantiza la autenticidad de la firma electrónica"
    )
    c.drawCentredString(
        width/2, 35,
        f"Generado el {firma.fecha_firma.strftime('%d/%m/%Y a las %H:%M:%S')}"
    )
    
    c.save()
    buffer.seek(0)
    return buffer
