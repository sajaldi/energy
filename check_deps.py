import sys
try:
    import fitz
    print("fitz (PyMuPDF) is installed")
except ImportError:
    print("fitz (PyMuPDF) is NOT installed")

try:
    import pytesseract
    print("pytesseract is installed")
except ImportError:
    print("pytesseract is NOT installed")

try:
    from pdf2image import convert_from_bytes
    print("pdf2image is installed")
except ImportError:
    print("pdf2image is NOT installed")
