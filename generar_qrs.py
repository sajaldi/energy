import qrcode
import os
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

def generar_etiquetas_pdf(archivo_salida="etiquetas_qr_3x2.pdf", prefijo="J7D", inicio=1, cantidad=12):
    # Configuración de la etiqueta (3x2 pulgadas)
    ANCHO_ETIQUETA, ALTO_ETIQUETA = 3.0 * inch, 2.0 * inch
    COLS, ROWS = 4, 3
    ANCHO_PAGINA, ALTO_PAGINA = ANCHO_ETIQUETA * COLS, ALTO_ETIQUETA * ROWS
    
    c = canvas.Canvas(archivo_salida, pagesize=(ANCHO_PAGINA, ALTO_PAGINA))
    actual = inicio
    temp_dir = 'tmp_qrs'
    if not os.path.exists(temp_dir): os.makedirs(temp_dir)

    while actual < (inicio + cantidad):
        for r in range(ROWS):
            for col in range(COLS):
                if actual >= (inicio + cantidad): break
                
                codigo_texto = f"{prefijo}{actual:04d}"
                x, y = col * ANCHO_ETIQUETA, (ROWS - 1 - r) * ALTO_ETIQUETA
                
                # Generar imagen QR
                qr = qrcode.QRCode(box_size=10, border=1)
                qr.add_data(codigo_texto)
                qr.make(fit=True)
                img_qr = qr.make_image(fill_color="black", back_color="white")
                
                qr_path = os.path.join(temp_dir, f"qr_{actual}.png")
                img_qr.save(qr_path)
                
                # --- Ajustes de Tamaño ---
                # Aumentamos el QR a 1.6 pulgadas (casi todo el alto disponible)
                tam_qr = 1.6 * inch
                margen_x = (ANCHO_ETIQUETA - tam_qr) / 2
                # Posicionamos el QR un poco más arriba (desde 0.4" del suelo de la etiqueta)
                c.drawImage(qr_path, x + margen_x, y + 0.4 * inch, width=tam_qr, height=tam_qr)
                
                # Aumentamos la letra a 24 puntos
                c.setFont("Helvetica-Bold", 24)
                # Texto centrado en la parte inferior (0.1" del suelo)
                c.drawCentredString(x + (ANCHO_ETIQUETA / 2), y + 0.1 * inch, codigo_texto)
                
                # Líneas guía de corte (gris muy suave)
                c.setStrokeColorRGB(0.92, 0.92, 0.92)
                c.rect(x, y, ANCHO_ETIQUETA, ALTO_ETIQUETA)
                
                actual += 1
                
        c.showPage()
        
    c.save()
    
    # Limpiar temporales
    for f in os.listdir(temp_dir): os.remove(os.path.join(temp_dir, f))
    os.rmdir(temp_dir)
    
    print(f"✅ Generadas {cantidad} etiquetas en {archivo_salida}")

if __name__ == "__main__":
    generar_etiquetas_pdf(cantidad=100)
