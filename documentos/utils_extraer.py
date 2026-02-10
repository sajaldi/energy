import os
import tempfile
import logging
import io

logger = logging.getLogger(__name__)

def extract_metadata_from_file(file_content, filename):
    file_ext = os.path.splitext(filename)[1].lower()
    
    extracted_data = {
        'file_name': filename,
        'extension': file_ext,
        'pages': 0,
        'text_preview': '',
        'metadata': {}
    }

    if not file_content:
        logger.warning(f"Extracción fallida: Archivo {filename} vacío.")
        return extracted_data

    if file_ext == '.pdf':
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=file_content, filetype="pdf")
            extracted_data['pages'] = len(doc)
            extracted_data['metadata'] = doc.metadata
            
            full_text = ""
            for i in range(min(5, len(doc))): # Revisar hasta 5 páginas
                # Intentar varios modos si el básico falla
                page_text = doc.load_page(i).get_text("text").strip()
                if not page_text:
                    page_text = doc.load_page(i).get_text("blocks")
                    # Convertir bloques a texto si es necesario
                    if page_text:
                        page_text = "\n".join([b[4] for b in page_text if isinstance(b, (list, tuple)) and len(b) > 4])
                
                full_text += (page_text or "") + "\n"
            
            extracted_data['text_preview'] = full_text.strip()[:5000]
            doc.close()

            if not extracted_data['text_preview']:
                logger.info(f"PyMuPDF no obtuvo texto para {filename}, intentando fallbacks...")
        except Exception as e:
            logger.error(f"Error PyMuPDF en {filename}: {e}")

        # Fallback 1: pdfplumber (mejor para algunos formatos que fitz)
        if not extracted_data.get('text_preview'):
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                    extracted_data['pages'] = len(pdf.pages)
                    text = ""
                    for page in pdf.pages[:5]:
                        text += (page.extract_text() or "") + "\n"
                    extracted_data['text_preview'] = text.strip()[:5000]
                if extracted_data['text_preview']:
                    logger.info(f"Texto extraído exitosamente con pdfplumber para {filename}")
            except Exception as e:
                logger.error(f"Error pdfplumber en {filename}: {e}")

        # Fallback 2: OCR (solo si tesseract está disponible)
        if not extracted_data.get('text_preview'):
            try:
                from pdf2image import convert_from_bytes
                import pytesseract
                # Advertencia: Esto requiere tesseract-ocr instalado en el SO
                images = convert_from_bytes(file_content, first_page=1, last_page=2)
                ocr_text = ""
                for img in images:
                    ocr_text += pytesseract.image_to_string(img) + "\n"
                extracted_data['text_preview'] = "(OCR) " + ocr_text.strip()[:5000]
            except Exception as e_ocr:
                # No logueamos error fuerte aquí porque es común que no esté tesseract
                pass

    elif file_ext in ['.docx', '.doc']:
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_content))
            extracted_data['pages'] = len(doc.sections)
            text = "\n".join([p.text for p in doc.paragraphs[:200]])
            extracted_data['text_preview'] = text.strip()[:5000]
        except Exception as e:
            logger.error(f"Error DOCX en {filename}: {e}")

    # Limpieza final: si todo falló, poner un mensaje claro o dejarlo vacío
    if not extracted_data.get('text_preview'):
        extracted_data['text_preview'] = "" # Mantener vacío para que el template use el default

    return extracted_data
