import os
import time
from datetime import datetime


def download_tickets_auto_excel(username, password, company_name, download_dir="downloads"):
    """
    Descarga el archivo Excel de tickets desde SIG GIA.
    NO aplica filtros de fecha — descarga la vista por defecto.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: Playwright no está instalado. Ejecute 'pip install playwright && playwright install chromium'")
        return None

    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, ignore_https_errors=True, viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        print(f"[{datetime.now()}] Navegando a SIG GIA...")
        page.goto("https://sig.gia.mx/webapp/seguridad/entrar", timeout=90000)

        # Login
        print("Realizando login...")
        page.fill("input#usaurio", username)
        page.fill("input#combinacion", password)

        # Seleccionar empresa
        page.click("div#select-simpleSelect")
        page.click(f"li[role='option']:has-text('{company_name}')")

        # Click Ingresar
        page.click("button:has-text('INGRESAR')")

        # Esperar a que cargue el dashboard
        page.wait_for_selector("text=Solicitudes", timeout=60000)
        print("Login exitoso.")

        # Navegar a SSA
        page.click("text=Solicitudes")
        time.sleep(1)

        # Click en Seguimiento de solicitud de atención
        page.click("text=Seguimiento de solicitud de atención")

        # Esperar a que cargue la página con los datos por defecto
        # (sin activar búsqueda avanzada, sin fechas)
        page.wait_for_selector("button#btnSolicitudesExcel", timeout=60000)
        time.sleep(3)
        print("Navegado a SSA Seguimiento. Descargando Excel con vista por defecto...")

        # Exportar Excel
        print("Iniciando descarga de Excel...")
        try:
            with page.expect_download(timeout=120000) as download_info:
                page.click("button#btnSolicitudesExcel", force=True)

            download = download_info.value
            file_name = f"tickets_auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            file_path = os.path.join(download_dir, file_name)
            download.save_as(file_path)

            print(f"Archivo descargado en: {file_path}")
            browser.close()
            return file_path
        except Exception as e:
            print(f"Error durante la descarga: {e}")
            browser.close()
            return None
