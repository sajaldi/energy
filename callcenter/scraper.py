import os
import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
import pandas as pd

def download_tickets_excel(username, password, company_name, days=2, download_dir="downloads"):
    """
    Descarga el archivo Excel de tickets desde la página de SIG GIA.
    Retorna la ruta al archivo descargado.
    """
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    with sync_playwright() as p:
        # Usar chromium con headless=True para el servidor
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print(f"[{datetime.now()}] Navegando a SIG GIA...")
        page.goto("https://sig.gia.mx/webapp/seguridad/entrar")

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
        # Usar un selector más robusto para el menú
        page.click("text=Solicitudes")
        time.sleep(1) # Pequeña espera para la animación del menú
        
        # Click en Seguimiento de solicitud de atención
        # El texto exacto es importante
        page.click("text=Seguimiento de solicitud de atención")
        
        # Esperar a que cargue la página de Seguimiento
        page.wait_for_selector("input.MuiSwitch-input", timeout=60000)
        print("Navegado a SSA Seguimiento.")

        # Búsqueda avanzada
        # El switch es un input dentro de un span
        page.click("input.MuiSwitch-input")
        print("Búsqueda avanzada activada. Esperando campos de fecha...")
        
        # Esperar a que aparezcan los inputs de fecha (suelen tener un placeholder o estar dentro de un MuiFormControl)
        page.wait_for_selector("input.MuiInputBase-input", timeout=30000)
        time.sleep(1) # Un segundo extra para asegurar que el JS los habilitó
        
        # Calcular fechas
        end_date = datetime.now().strftime("%d/%m/%Y")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%d/%m/%Y")
        
        print(f"Aplicando filtro de fechas: {start_date} al {end_date}")
        
        # Seleccionar inputs de fecha por su etiqueta o índice
        inputs = page.query_selector_all("input.MuiInputBase-input")
        
        if len(inputs) >= 2:
            # Inicio (normalmente el primero)
            inputs[0].click()
            page.keyboard.press("Control+A")
            page.keyboard.type(start_date)
            page.keyboard.press("Enter") # Asegurar que el cambio se registre
            
            # Final (normalmente el segundo)
            inputs[1].click()
            page.keyboard.press("Control+A")
            page.keyboard.type(end_date)
            page.keyboard.press("Enter")
            
            # Aplicar filtros
            print("Clic en Aplicar filtros...")
            page.click("button#btnBuscar")
            
            # Esperar a que aparezca algún indicador de carga o simplemente esperar un poco
            print("Filtros aplicados. Esperando a que el botón de Excel sea clickeable...")
            page.wait_for_selector("button#btnSolicitudesExcel", timeout=60000)
            time.sleep(5) # Tiempo de gracia para que la tabla se pueble
            
            # Exportar Excel
            print("Iniciando descarga de Excel...")
            with page.expect_download(timeout=120000) as download_info:
                # A veces el botón está deshabilitado mientras carga
                page.click("button#btnSolicitudesExcel", force=True)
            
            download = download_info.value
            file_name = f"tickets_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            file_path = os.path.join(download_dir, file_name)
            download.save_as(file_path)
            
            print(f"Archivo descargado en: {file_path}")
            browser.close()
            return file_path
        else:
            print("No se encontraron los campos de fecha.")
            browser.close()
            return None

if __name__ == "__main__":
    # Prueba local
    download_tickets_excel("saul.alvarado", "S@4l2689*", "Centro Cívico Gubernamental de Honduras")
