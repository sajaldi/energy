import os
import time
from datetime import datetime, timedelta
import pandas as pd
from django.conf import settings

def download_tickets_excel(username, password, company_name, days=2, download_dir="downloads"):
    """
    Descarga el archivo Excel de tickets desde la página de SIG GIA.
    Retorna la ruta al archivo descargado.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: Playwright no está instalado. Ejecute 'pip install playwright && playwright install chromium'")
        return None

    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    with sync_playwright() as p:
        # Usar chromium con headless=True para el servidor
        browser = p.chromium.launch(headless=True)
        # Forzar un viewport de escritorio para evitar que el menú lateral colapse (hamburger menu) ocultando 'Solicitudes'
        context = browser.new_context(accept_downloads=True, ignore_https_errors=True, viewport={'width': 1920, 'height': 1080})
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
        
        # Esperar a que aparezcan los inputs de fecha
        try:
            page.wait_for_selector("input.MuiInputBase-input", timeout=30000)
            time.sleep(2) # Segundo extra para asegurar que el JS los habilitó
            
            # Tomar screenshot para depuración
            # page.screenshot(path="downloads/debug_busqueda_avanzada.png")
            # print("Screenshot guardado en downloads/debug_busqueda_avanzada.png")
        except Exception as e:
            # page.screenshot(path="downloads/error_busqueda_avanzada.png")
            print(f"Error esperando campos de fecha: {e}")
            browser.close()
            return None
        
        # Calcular fechas
        end_date = datetime.now().strftime("%d/%m/%Y")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%d/%m/%Y")
        
        print(f"Aplicando filtro de fechas: {start_date} al {end_date}")
        
        # Seleccionar inputs de fecha por su etiqueta o índice
        # Intentar ser más específico para evitar inputs ocultos
        inputs = page.query_selector_all("input.MuiInputBase-input:not([type='hidden'])")
        
        if len(inputs) >= 2:
            try:
                # Inicio
                inputs[0].scroll_into_view_if_needed()
                inputs[0].click(force=True) # Usar force=True si está cubierto
                page.keyboard.press("Control+A")
                page.keyboard.type(start_date)
                page.keyboard.press("Enter")
                
                # Final
                inputs[1].scroll_into_view_if_needed()
                inputs[1].click(force=True)
                page.keyboard.press("Control+A")
                page.keyboard.type(end_date)
                page.keyboard.press("Enter")
                
                time.sleep(1)
                # page.screenshot(path="downloads/debug_fechas_aplicadas.png")
            except Exception as e:
                # page.screenshot(path="downloads/error_llenando_fechas.png")
                print(f"Error llenando fechas: {e}")
                browser.close()
                return None
            
            # Aplicar filtros
            print("Clic en Aplicar filtros...")
            page.click("button#btnBuscar")
            
            # Esperar a que la tabla se actualice y el botón de Excel sea clickeable
            print("Filtros aplicados. Esperando a que el botón de Excel sea clickeable...")
            try:
                page.wait_for_selector("button#btnSolicitudesExcel", timeout=60000)
                time.sleep(5) # Tiempo de gracia para que la tabla se pueble
                # page.screenshot(path="downloads/debug_tabla_cargada.png")
            except:
                # page.screenshot(path="downloads/error_esperando_excel.png")
                print("El botón de Excel no apareció a tiempo.")
                browser.close()
                return None
            
            # Exportar Excel
            print("Iniciando descarga de Excel...")
            try:
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
            except Exception as e:
                print(f"Error durante la descarga: {e}")
                browser.close()
                return None
        else:
            print(f"No se encontraron suficientes campos de fecha. Encontrados: {len(inputs)}")
            # page.screenshot(path="downloads/error_inputs_insuficientes.png")
            browser.close()
            return None

def sync_individual_ticket(username, password, company_name, ticket_folio, fecha_solicitud):
    """
    Robot que sincroniza un ticket individual en SIG.
    Sigue los pasos: Login -> SSA -> Búsqueda -> Filtros -> Ojito.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "error", "message": "Playwright no está instalado."}

    # Calcular rango de fechas (+/- 1 día)
    start_date_dt = fecha_solicitud - timedelta(days=1)
    end_date_dt = fecha_solicitud + timedelta(days=1)
    
    start_date = start_date_dt.strftime("%d/%m/%Y")
    end_date = end_date_dt.strftime("%d/%m/%Y")

    with sync_playwright() as p:
        # Usamos headless=True por defecto, pero permitimos depuración
        browser = p.chromium.launch(headless=True)
        # Forzar viewport para evitar ocultamiento de menú en modo responsivo
        context = browser.new_context(ignore_https_errors=True, viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        try:
            print(f"Sincronizando ticket {ticket_folio}...")
            # 1. Login
            page.goto("https://sig.gia.mx/webapp/seguridad/entrar")
            page.wait_for_selector("input#usaurio", timeout=30000)
            page.fill("input#usaurio", username)
            page.fill("input#combinacion", password)
            page.click("div#select-simpleSelect")
            page.click(f"li[role='option']:has-text('{company_name}')")
            page.click("button:has-text('INGRESAR')")
            
            # 2. Navegar a SSA Seguimiento
            page.wait_for_selector("text=Solicitudes", timeout=60000)
            page.goto("https://sig.gia.mx/webapp/admin/Solicitud/SeguimientoAtencion")
            
            # 3. Activar búsqueda avanzada (Switch)
            # Obligatorio para ver los campos de fecha y folio
            page.wait_for_selector("input.MuiSwitch-input", timeout=30000)
            page.click("input.MuiSwitch-input")
            time.sleep(2)

            # 4. Ingresar ticket en id="busqueda"
            page.wait_for_selector("id=busqueda", timeout=30000)
            page.click("id=busqueda")
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.fill("id=busqueda", ticket_folio)
            print(f"Ticket {ticket_folio} ingresado.")

            # 5. Ingresar fechas (Inicio y Final)
            inicio_selector = "div:has(> label:has-text('Inicio')) input"
            final_selector = "div:has(> label:has-text('Final')) input"
            
            # Fecha Inicio
            page.click(inicio_selector)
            page.keyboard.press("Control+A")
            page.keyboard.type(start_date)
            page.keyboard.press("Enter")
            print(f"Fecha Inicio {start_date} configurada.")
            
            # Fecha Final
            page.click(final_selector)
            page.keyboard.press("Control+A")
            page.keyboard.type(end_date)
            page.keyboard.press("Enter")
            print(f"Fecha Final {end_date} configurada.")
            
            time.sleep(1)

            # 6. Aplicar filtros (Botón azul)
            # El ID suele ser btnBuscar
            page.click("id=btnBuscar")
            print("Clic en Aplicar filtros realizado.")
            
            # 7. Esperar a que la fila específica del ticket aparezca en la tabla
            print(f"Esperando a que la fila con el folio {ticket_folio} sea visible en la tabla...")
            row_selector = f"tr:has(td:text('{ticket_folio}'))"
            
            try:
                # Esperamos hasta 30 segundos a que aparezca la fila correcta
                page.wait_for_selector(row_selector, timeout=30000, state="visible")
                print(f"Fila del ticket {ticket_folio} encontrada.")
                
                # Definimos el botón 'ojito' DENTRO de esa fila específica
                specific_row = page.locator(row_selector)
                ojito_selector = "button[title='Seguimiento']"
                icon_selector = "svg[data-testid='VisibilityIcon']"
                
                # Intentamos por title primero dentro de la fila
                if specific_row.locator(ojito_selector).count() > 0:
                    specific_row.locator(ojito_selector).click()
                    print("Ojito clickeado por title en la fila correcta.")
                # Si no, por el icono de visibilidad
                elif specific_row.locator(icon_selector).count() > 0:
                    specific_row.locator(icon_selector).locator("xpath=..").click()
                    print("Ojito clickeado por icono en la fila correcta.")
                else:
                    # Fallback si no encontramos el botón específico pero la fila está
                    messages_err = f"Se encontró la fila de {ticket_folio} pero no el botón de seguimiento."
                    print(messages_err)
                    page.screenshot(path=os.path.join(settings.BASE_DIR, "downloads", f"error_row_{ticket_folio}.png"))
                    raise Exception(messages_err)
                    
            except Exception as e:
                print(f"Error al buscar la fila específica o el botón: {e}")
                # Tomamos una captura de debug para ver qué hay en la tabla
                debug_path = os.path.join(settings.BASE_DIR, "downloads", f"debug_table_{ticket_folio}.png")
                page.screenshot(path=debug_path)
                raise Exception(f"No se pudo localizar el ticket {ticket_folio} en los resultados tras filtrar. Verifique si el folio existe y está en el rango de fechas.")

            time.sleep(5) # Esperar a que cargue la vista de seguimiento
            
            # --- NUEVA PARTE: Capturar Diagnóstico ---
            print("Accediendo a la captura de Diagnóstico...")
            try:
                # El primer botón 'CAPTURAR' en la vista de seguimiento suele ser el de Diagnóstico
                btn_capturar = page.locator("button:has-text('CAPTURAR')").first
                
                if btn_capturar.count() > 0:
                    btn_capturar.click()
                    print("Botón 'CAPTURAR' de Diagnóstico clickeado.")
                    
                    # Esperar al modal (título del modal)
                    page.wait_for_selector("text=Diagnóstico", timeout=15000)
                    time.sleep(2)
                    
                    # Seleccionar el único textarea que suele haber en este modal
                    textarea = page.locator("div[role='dialog'] textarea, textarea").first
                    if textarea.count() > 0:
                        # Hacemos clic, vamos al final y agregamos el punto
                        textarea.click()
                        page.keyboard.press("End")
                        page.keyboard.type(".")
                        print("Punto agregado al diagnóstico.")
                        
                        # Guardar cambio (Botón APLICAR dentro del modal)
                        # Restringimos al diálogo para no confundir con 'Aplicar filtros' del fondo
                        btn_aplicar = page.locator("div[role='dialog'] button:has-text('APLICAR')")
                        if btn_aplicar.count() > 0:
                            btn_aplicar.first.click()
                            print("Clic en APLICAR realizado.")
                            time.sleep(3)
                    else:
                        print("No se encontró el textarea en el modal.")
                else:
                    print("No se encontró el botón CAPTURAR asociado a la fila de Diagnóstico.")
            except Exception as e:
                print(f"Error en fase de diagnóstico: {e}")
            
            screenshot_path = os.path.join(settings.BASE_DIR, "downloads", f"final_sync_{ticket_folio}.png")
            page.screenshot(path=screenshot_path)
            
            browser.close()
            return {"status": "success", "message": "Sincronización exitosa. El robot llegó hasta el detalle del ticket.", "screenshot": screenshot_path}

        except Exception as e:
            # Tomar screenshot de error
            error_screenshot = os.path.join(settings.BASE_DIR, "downloads", f"error_robot_{ticket_folio}.png")
            print(f"Error en el robot: {e}")
            page.screenshot(path=error_screenshot)
            browser.close()
            return {"status": "error", "message": str(e), "screenshot": error_screenshot}

if __name__ == "__main__":

    # Prueba local
    import os
    download_tickets_excel("saul.alvarado", os.environ.get('PASS_SIG', ''), "Centro Cívico Gubernamental de Honduras")
