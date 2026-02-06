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
        return extracted_data

    if file_ext == '.pdf':
        try:
            import fitz  # PyMuPDF
            # Usar stream para evitar archivos temporales y problemas de permisos en Windows
            doc = fitz.open(stream=file_content, filetype="pdf")
            extracted_data['pages'] = len(doc)
            extracted_data['metadata'] = doc.metadata
            
            full_text = ""
            for i in range(min(3, len(doc))):
                full_text += doc.load_page(i).get_text() + "\n"
            
            extracted_data['text_preview'] = full_text[:5000]

            # Fallback OCR si está vacío
            if not extracted_data['text_preview'].strip():
                try:
                    from pdf2image import convert_from_bytes
                    import pytesseract
                    images = convert_from_bytes(file_content, first_page=1, last_page=1)
                    if images:
                        ocr_text = pytesseract.image_to_string(images[0])
                        extracted_data['text_preview'] = "(OCR) " + ocr_text[:5000]
                except Exception as e_ocr:
                    logger.error(f"OCR Error: {e_ocr}")
            
            doc.close()
        except Exception as e:
            logger.error(f"Error PyMuPDF: {e}")
            # Intento final con pdfplumber si fitz falla
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                    extracted_data['pages'] = len(pdf.pages)
                    text = ""
                    for page in pdf.pages[:3]:
                        text += (page.extract_text() or "") + "\n"
                    extracted_data['text_preview'] = text[:5000]
            except Exception as e2:
                logger.error(f"Error pdfplumber: {e2}")

    elif file_ext == '.docx':
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_content))
            extracted_data['pages'] = len(doc.sections)
            text = "\n".join([p.text for p in doc.paragraphs[:100]])
            extracted_data['text_preview'] = text[:5000]
        except Exception as e:
            logger.error(f"Error DOCX: {e}")

    return extracted_data
