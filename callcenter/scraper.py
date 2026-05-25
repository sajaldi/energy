import os
import re
import time
from datetime import datetime, timedelta
import pandas as pd
from django.conf import settings

def download_tickets_excel(username, password, company_name, days=2, download_dir="downloads", fecha_inicio=None, fecha_fin=None):
    """
    Descarga el archivo Excel de tickets desde la página de SIG GIA.
    Retorna la ruta al archivo descargado.
    
    Args:
        fecha_inicio: Fecha inicio en formato dd/mm/yyyy (opcional, prioridad sobre days)
        fecha_fin: Fecha fin en formato dd/mm/yyyy (opcional, prioridad sobre days)
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
        
        # Calcular fechas: priorizar parámetros explícitos sobre days
        if fecha_inicio and fecha_fin:
            start_date = fecha_inicio
            end_date = fecha_fin
        else:
            end_date = datetime.now().strftime("%d/%m/%Y")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%d/%m/%Y")
        
        print(f"Aplicando filtro de fechas: {start_date} al {end_date}")
        
        # Selectores más robustos para los inputs de fecha (basados en sus etiquetas)
        inicio_selector = "div:has(> label:has-text('Inicio')) input"
        final_selector = "div:has(> label:has-text('Final')) input"

        try:
            # Esperar a que los inputs específicos sean visibles
            page.wait_for_selector(inicio_selector, timeout=20000)
            page.wait_for_selector(final_selector, timeout=20000)
            
            # Función helper para llenar y verificar el valor del input
            def fill_and_verify(selector, value, label):
                input_elem = page.locator(selector)
                input_elem.scroll_into_view_if_needed()
                input_elem.click(force=True)
                # Limpiar campo a fondo
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(value)
                page.keyboard.press("Enter")
                time.sleep(1.5) # Esperar procesamiento de JS
                
                # Verificación de valor extraído
                current_val = input_elem.input_value()
                if current_val != value:
                    print(f"[WARNING] El valor de {label} ({current_val}) no coincide con el solicitado ({value}). Reintentando...")
                    input_elem.click(force=True)
                    page.keyboard.press("Control+A")
                    page.keyboard.type(value)
                    page.keyboard.press("Enter")
                    time.sleep(1)
                else:
                    print(f"[OK] Fecha de {label} verificada: {current_val}")
            
            # Llenar y verificar ambas fechas
            fill_and_verify(inicio_selector, start_date, "Inicio")
            fill_and_verify(final_selector, end_date, "Final")
            
            time.sleep(2) # Espera de seguridad antes de aplicar filtros
            
            # Aplicar filtros
            print("Clic en Aplicar filtros...")
            page.click("button#btnBuscar")
            
            # Esperar a que la tabla se actualice (darle más tiempo al servidor)
            print("Filtros aplicados. Esperando carga de datos...")
            time.sleep(5)
            
            page.wait_for_selector("button#btnSolicitudesExcel", timeout=60000)
            print("Botón de Excel listo.")
            
        except Exception as e:
            print(f"Error durante el filtrado de fechas: {e}")
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
def pick_mui_datetime(page, dt):
    """Navega el MUI DateTimePicker para seleccionar fecha+hora exacta.
    Soporta calendarios en Inglés y Español.
    """
    target_day = str(dt.day)
    target_year = str(dt.year)
    hour_str = str(int(dt.strftime("%I")))   # 12h sin cero leading
    minute_str = dt.strftime("%M")
    ampm_str = dt.strftime("%p").upper()
    
    month_names_en = ["", "January", "February", "March", "April", "May", "June",
                      "July", "August", "September", "October", "November", "December"]
    month_names_es = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                      "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    target_month_en = month_names_en[dt.month]
    target_month_es = month_names_es[dt.month]

    print(f"[pick_mui_datetime] Iniciando selección visual de fecha: {target_day}/{dt.month}/{target_year} y hora: {hour_str}:{minute_str} {ampm_str}")

    # === FECHA ===
    try:
        page.get_by_role("button", name="change date").click()
        page.wait_for_timeout(1000)
    except Exception as e:
        print(f"[pick_mui_datetime] Error al abrir calendario: {e}")
        try:
            page.locator("button[aria-label='change date']").click()
            page.wait_for_timeout(1000)
        except Exception:
            pass

    # Intento 1: Seleccionar el día directamente si ya está en el mes/año correcto
    day_selected = False
    try:
        day_btn = page.get_by_role("button", name=target_day, exact=True).first
        if day_btn.count() > 0 and day_btn.is_visible():
            day_btn.click()
            print(f"[pick_mui_datetime] Día {target_day} seleccionado directamente.")
            day_selected = True
            page.wait_for_timeout(800)
    except Exception:
        pass

    if not day_selected:
        print("[pick_mui_datetime] No se pudo seleccionar el día directamente, intentando navegar año y mes...")
        # Ir a selección de año (click año actual en el header)
        current_year = datetime.now().year
        for y in [current_year, current_year - 1, current_year + 1]:
            try:
                btn = page.get_by_role("button", name=str(y)).first
                if btn.count() > 0 and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(500)
                    break
            except Exception:
                continue

        # Click año destino
        try:
            page.get_by_role("button", name=target_year, exact=True).first.click()
            page.wait_for_timeout(800)
        except Exception as e:
            print(f"[pick_mui_datetime] Error seleccionando año {target_year}: {e}")

        # Click mes destino
        try:
            month_btn = page.get_by_role("button", name=target_month_en, exact=True)
            if month_btn.count() > 0:
                month_btn.click()
                page.wait_for_timeout(500)
            else:
                month_btn = page.get_by_role("button", name=target_month_es, exact=True)
                if month_btn.count() > 0:
                    month_btn.click()
                    page.wait_for_timeout(500)
        except Exception as e:
            print(f"[pick_mui_datetime] Error seleccionando mes {target_month_es}: {e}")

        # Click día final
        try:
            page.get_by_role("button", name=target_day, exact=True).first.click()
            page.wait_for_timeout(800)
            print(f"[pick_mui_datetime] Día {target_day} seleccionado después de navegación.")
        except Exception as e:
            print(f"[pick_mui_datetime] Error crítico al hacer click en el día: {e}")

    # === HORA ===
    try:
        page.get_by_role("button", name="change time").click()
        page.wait_for_timeout(1000)
    except Exception as e:
        print(f"[pick_mui_datetime] Error al abrir selector de hora: {e}")
        try:
            page.locator("button[aria-label='change time']").click()
            page.wait_for_timeout(1000)
        except Exception:
            pass

    # AM/PM
    try:
        page.get_by_role("button", name=ampm_str).click()
        page.wait_for_timeout(500)
    except Exception as e:
        print(f"[pick_mui_datetime] No se pudo clickear AM/PM ({ampm_str}): {e}")

    # Hora
    try:
        hour_btn = page.get_by_role("button", name=hour_str, exact=True).first
        if hour_btn.count() > 0:
            hour_btn.click()
            page.wait_for_timeout(500)
        else:
            page.get_by_text(hour_str, exact=True).first.click()
            page.wait_for_timeout(500)
    except Exception as e:
        print(f"[pick_mui_datetime] No se pudo clickear hora {hour_str}: {e}")

    # Minuto
    try:
        minute_btn = page.get_by_role("button", name=minute_str, exact=True)
        if minute_btn.count() > 0 and minute_btn.first.is_visible():
            minute_btn.first.click()
            print(f"[pick_mui_datetime] Minuto {minute_str} seleccionado por botón exacto.")
        else:
            minute_int = int(minute_str)
            rounded_minute = 5 * round(minute_int / 5)
            if rounded_minute == 60:
                rounded_minute = 55
            rounded_minute_str = f"{rounded_minute:02d}"
            
            rounded_btn = page.get_by_role("button", name=rounded_minute_str, exact=True)
            if rounded_btn.count() > 0:
                rounded_btn.first.click()
                print(f"[pick_mui_datetime] Minuto {minute_str} redondeado a {rounded_minute_str} y seleccionado.")
            else:
                page.locator('div:nth-child(11) > div').first().click()
        page.wait_for_timeout(500)
    except Exception as e:
        print(f"[pick_mui_datetime] Error al seleccionar minuto: {e}")


def subir_evidencias(page, evidencias):
    """Sube archivos a la sección Adjuntos.
    Usa expect_file_chooser para manejar correctamente el botón de carga personalizado (span#confirmar / Agregar).
    """
    if not evidencias:
        print("No hay evidencias para subir.")
        return

    for i, ev in enumerate(evidencias):
        print(f"Subiendo evidencia {i+1}/{len(evidencias)}: {ev['descripcion'][:60]}...")
        try:
            # 1. Llenar descripción del adjunto
            desc = page.locator("#adjDescripcion")
            desc.scroll_into_view_if_needed(timeout=15000)
            desc.click()
            desc.fill(ev['descripcion'])
            time.sleep(1.0)
            
            # 2. Cargar el archivo usando el file chooser al hacer click en el botón Agregar
            print("Esperando botón Agregar...")
            agregar_btn = page.locator("span#confirmar, button:has-text('Agregar'), [label='Agregar']").first
            agregar_btn.scroll_into_view_if_needed(timeout=10000)
            
            # Usar expect_file_chooser para interceptar el diálogo de archivos
            with page.expect_file_chooser() as fc_info:
                agregar_btn.click()
            
            file_chooser = fc_info.value
            file_chooser.set_files(ev['path'])
            print(f"Evidencia {i+1} cargada mediante file chooser.")
            time.sleep(3.0)
            
        except Exception as e:
            print(f"Error en evidencia {i+1}: {e}")
            # Intentar fallback directo si hay un input file oculto en la página
            try:
                print("Intentando fallback directo a input[type='file']...")
                input_file = page.locator("input[type='file']").first
                if input_file.count() > 0:
                    input_file.set_input_files(ev['path'])
                    print("Evidencia subida exitosamente vía input[type='file'] fallback.")
                    time.sleep(3.0)
                else:
                    raise Exception("No se encontró input[type='file']")
            except Exception as e_fallback:
                print(f"Fallback también falló: {e_fallback}")
                page.screenshot(path=os.path.join(settings.BASE_DIR, "downloads", f"error_adjuntos_{i+1}.png"))


def sync_individual_ticket(username, password, company_name, ticket_folio, fecha_solicitud, diagnostico_django, actividades_django, observaciones_django, observaciones_usuario_django, fecha_observaciones_usuario, fecha_cierre, evidencias=None):
    """
    Robot que sincroniza un ticket individual en SIG GIA.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "error", "message": "Playwright no está instalado."}

    from datetime import timezone
    tz_honduras = timezone(timedelta(hours=-6))
    fecha_local = fecha_solicitud.astimezone(tz_honduras)

    start_date = fecha_local.replace(day=1).strftime("%d/%m/%Y")
    end_date   = fecha_local.strftime("%d/%m/%Y")
    print(f"Rango de fechas: {start_date} al {end_date} (hora local Honduras)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True, viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        def take_screenshot(page, step_name):
            path = os.path.join(settings.BASE_DIR, "downloads", f"step_{step_name}_{ticket_folio}.png")
            page.screenshot(path=path)
            print(f"Captura realizada: {path}")

        try:
            print(f"Sincronizando ticket {ticket_folio}...")

            # ========== 1. LOGIN ==========
            print("Paso 1: Login...")
            page.goto("https://sig.gia.mx/webapp/seguridad/entrar")
            page.wait_for_selector("#usaurio", timeout=30000)
            page.get_by_role("textbox", name="Usuario...").fill(username)
            page.get_by_role("textbox", name="Contraseña...").fill(password)
            page.locator("#select-simpleSelect").click()
            time.sleep(0.5)
            page.get_by_text(company_name).first.click()
            page.get_by_role("button", name="INGRESAR").click()
            page.wait_for_selector("text=Solicitudes", timeout=60000)
            print("Login exitoso.")
            take_screenshot(page, "01_login_exitoso")

            # ========== 2. NAVEGAR A SSA ==========
            print("Paso 2: Navegando a SSA...")
            try:
                page.get_by_role("link", name="Solicitudes").click()
            except Exception:
                page.get_by_text("Solicitudes").first.click()
            time.sleep(3)
            
            try:
                page.get_by_role("link", name="SSA Seguimiento de solicitud").click()
            except Exception:
                print("Link SSA no encontrado, intentando con texto...")
                page.get_by_text("Seguimiento de solicitud").first.click()
            page.wait_for_selector("input.MuiSwitch-input", timeout=60000)
            print("Navegado a SSA Seguimiento.")

            # ========== 3. BÚSQUEDA AVANZADA ==========
            page.locator("input.MuiSwitch-input").click()
            time.sleep(3)
            print("Búsqueda avanzada activada.")

            # ========== 4. CONFIGURAR FILTROS ==========
            # Llenar la búsqueda avanzada con el folio del ticket para que cargue instantáneamente
            print("Buscando el campo de búsqueda avanzada...")
            try:
                search_input = page.locator("#busqueda")
                if search_input.count() == 0:
                    search_input = page.get_by_role("textbox", name="Busqueda avanzada").first
                
                search_input.click()
                search_input.fill(ticket_folio)
                print(f"Búsqueda avanzada filtrada por folio: {ticket_folio}")
            except Exception as e:
                print(f"No se pudo escribir en el campo de búsqueda avanzada: {e}")
            
            take_screenshot(page, "02_busqueda_aplicada")

            try:
                page.get_by_role("button", name="Aplicar filtros").click()
            except Exception:
                page.locator("id=btnBuscar").click()
            print("Filtros aplicados. Esperando carga de tabla...")
            time.sleep(3)

            # ========== 5. ESPERAR TABLA Y CLIC OJITO ==========
            row_selector = f"tr:has(td:text('{ticket_folio}'))"
            try:
                page.wait_for_selector(row_selector, timeout=120000, state="visible")
                print(f"Ticket {ticket_folio} encontrado en la tabla.")
            except Exception:
                debug_path = os.path.join(settings.BASE_DIR, "downloads", f"debug_table_{ticket_folio}.png")
                page.screenshot(path=debug_path)
                raise Exception(
                    f"No se pudo localizar el ticket {ticket_folio} en los resultados. "
                    f"Rango: {start_date} - {end_date}. Ver screenshot: {debug_path}"
                )

            specific_row = page.locator(row_selector)
            try:
                ojito_title = specific_row.locator("button[title='Seguimiento']")
                ojito_icon = specific_row.locator("svg[data-testid='VisibilityIcon']")

                if ojito_title.count() > 0:
                    ojito_title.click()
                    print("Ojito clickeado por title.")
                elif ojito_icon.count() > 0:
                    ojito_icon.locator("xpath=..").click()
                    print("Ojito clickeado por icono.")
                else:
                    debug_path = os.path.join(settings.BASE_DIR, "downloads", f"error_row_{ticket_folio}.png")
                    page.screenshot(path=debug_path)
                    raise Exception("Botón de seguimiento no encontrado en la fila.")
            except Exception as e:
                debug_path = os.path.join(settings.BASE_DIR, "downloads", f"debug_table_{ticket_folio}.png")
                page.screenshot(path=debug_path)
                raise Exception(f"No se pudo localizar el botón de seguimiento: {e}")

            time.sleep(3)
            take_screenshot(page, "03_ticket_abierto")

            # ========== 6. CAPTURAS ==========
            def capturar_seccion(page, indice, texto, nombre_seccion):
                print(f"Accediendo a captura de {nombre_seccion}...")
                try:
                    btn = page.get_by_role("button", name="Capturar").nth(indice)
                    if btn.count() > 0:
                        btn.click()
                        print(f"Botón CAPTURAR ({nombre_seccion}) clickeado.")
                        time.sleep(3)

                        textarea = page.locator("textarea").first
                        if textarea.count() > 0:
                            textarea.click()
                            textarea.fill(str(texto or ".")[:500])
                            print(f"Texto ingresado en {nombre_seccion}: {(str(texto or '')[:60])}...")
                            time.sleep(1)

                            page.get_by_role("button", name="Aplicar").first.click()
                            print(f"Clic en APLICAR ({nombre_seccion}) realizado.")
                            time.sleep(3)
                            take_screenshot(page, f"04_captura_{nombre_seccion}_exitosa")
                        else:
                            print(f"No se encontró textarea en modal de {nombre_seccion}.")
                    else:
                        print(f"No se encontró botón CAPTURAR #{indice} ({nombre_seccion}).")
                except Exception as e:
                    print(f"Error en captura de {nombre_seccion}: {e}")

            capturar_seccion(page, 0, diagnostico_django, "Diagnóstico")
            capturar_seccion(page, 1, actividades_django, "Actividades")
            capturar_seccion(page, 2, observaciones_django, "Observaciones")

            # ========== 7. ASIGNAR / CERRO (MODAL CIERRE) ==========
            # DESACTIVADO TEMPORALMENTE: Cambiado a `if False` para enfocar las pruebas en la subida de adjuntos
            # como lo solicitó el usuario. Para reactivarlo más adelante, simplemente cambiar a `if fecha_cierre:`
            if False:  # fecha_cierre:
                print("Accediendo a Asignar/Cierre...")
                try:
                    # Abrir el modal "Cerro" (4to botón Asignar)
                    page.get_by_role("button", name="Asignar").nth(3).click(timeout=60000)
                    time.sleep(2.5)
                    take_screenshot(page, "05_modal_cierre_abierto")

                    fecha_local_cierre = fecha_cierre.astimezone(tz_honduras)
                    
                    # Rellenado 100% visual mediante el calendario y reloj de MUI.
                    # No intentamos escribir directamente ya que no son elementos del tipo input interactivos.
                    pick_mui_datetime(page, fecha_local_cierre)
                    
                    time.sleep(1)

                    # Buscar y seleccionar responsable por defecto "Oscar Posadas Mendieta"
                    try:
                        page.get_by_role("combobox").get_by_role("button").click()
                    except Exception:
                        page.locator("div[role='dialog'] button").nth(2).click()
                    time.sleep(1.5)

                    page.get_by_role("textbox", name="Filtrar").fill("oscar")
                    time.sleep(2.5)

                    # Hacer doble click en "Oscar Posadas Mendieta" para seleccionarlo
                    page.get_by_role("gridcell", name="Oscar Posadas Mendieta").first.dblclick()
                    time.sleep(1.5)

                    take_screenshot(page, "06_modal_cierre_llenado")

                    # Click en Aplicar para guardar y cerrar modal
                    page.get_by_role("button", name="Aplicar").click()
                    print(f"Asignar/Cierre guardado: {fecha_local_cierre.strftime('%d/%m/%Y %I:%M %p')} - Oscar Posadas Mendieta")
                    time.sleep(3)

                except Exception as e:
                    print(f"Error en fase de Asignar/Cierre: {e}")
                    take_screenshot(page, "05_error_cierre")
                    # Cerrar usando el botón Salir / SALIR del modal para evitar que obstruya la página
                    try:
                        salir_btn = page.get_by_role("button", name="Salir")
                        if salir_btn.count() > 0:
                            salir_btn.first.click()
                        else:
                            salir_btn_upper = page.get_by_role("button", name="SALIR")
                            if salir_btn_upper.count() > 0:
                                salir_btn_upper.first.click()
                    except Exception as e_salir:
                        print(f"No se pudo hacer clic en Salir para cerrar modal: {e_salir}")
                    time.sleep(1.5)
            else:
                print("fecha_cierre no proporcionada, saltando Asignar/Cierre.")

            # ========== 8. ADJUNTOS (EVIDENCIAS) ==========
            # NO presionar Escape aquí: eso cierra el panel del ticket y vuelve a la tabla
            time.sleep(1)
            take_screenshot(page, "07_antes_adjuntos")
            subir_evidencias(page, evidencias)

            # ========== 9. FINALIZAR ==========
            screenshot_path = os.path.join(settings.BASE_DIR, "downloads", f"final_sync_{ticket_folio}.png")
            page.screenshot(path=screenshot_path)
            browser.close()
            return {"status": "success", "message": "Sincronización exitosa.", "screenshot": screenshot_path}

        except Exception as e:
            error_screenshot = os.path.join(settings.BASE_DIR, "downloads", f"error_robot_{ticket_folio}.png")
            print(f"Error en el robot: {e}")
            page.screenshot(path=error_screenshot)
            browser.close()
            return {"status": "error", "message": str(e), "screenshot": error_screenshot}

def download_tickets_by_folio_list(username, password, company_name, folios_list, download_dir="downloads"):
    """
    Descarga los archivos Excel de tickets específicos desde SIG GIA.
    Navega por cada folio, busca y descarga el Excel individual.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: Playwright no está instalado.")
        return []

    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    downloaded_files = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, ignore_https_errors=True, viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        print(f"[{datetime.now()}] Iniciando descarga masiva por folios...")
        page.goto("https://sig.gia.mx/webapp/seguridad/entrar", timeout=90000)

        # 1. Login
        page.fill("input#usaurio", username)
        page.fill("input#combinacion", password)
        page.click("div#select-simpleSelect")
        page.click(f"li[role='option']:has-text('{company_name}')")
        page.click("button:has-text('INGRESAR')")
        page.wait_for_selector("text=Solicitudes", timeout=60000)

        # 2. Navegar a SSA Seguimiento
        page.goto("https://sig.gia.mx/webapp/admin/Solicitud/SeguimientoAtencion")
        page.wait_for_selector("input.MuiSwitch-input", timeout=60000)
        page.click("input.MuiSwitch-input") # Activar búsqueda avanzada
        time.sleep(2)

        for folio in folios_list:
            folio = folio.strip()
            if not folio: continue
            
            print(f"Buscando ticket: {folio}")
            try:
                # Limpiar y llenar campo de búsqueda
                page.wait_for_selector("id=busqueda", timeout=20000)
                page.click("id=busqueda")
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.fill("id=busqueda", folio)
                
                # Aplicar filtros
                page.click("id=btnBuscar")
                
                # Esperar a que el botón de Excel esté listo (significa que la tabla cargó)
                # Damos un tiempo para que el servidor procese
                time.sleep(3)
                page.wait_for_selector("button#btnSolicitudesExcel", timeout=30000)
                
                # Descargar Excel
                with page.expect_download(timeout=60000) as download_info:
                    page.click("button#btnSolicitudesExcel", force=True)
                
                download = download_info.value
                file_name = f"sync_{folio}_{datetime.now().strftime('%H%M%S')}.xlsx"
                file_path = os.path.join(download_dir, file_name)
                download.save_as(file_path)
                downloaded_files.append(file_path)
                print(f"Descargado: {folio}")
                
            except Exception as e:
                print(f"Error descargando {folio}: {e}")
                continue

        browser.close()
        return downloaded_files

if __name__ == "__main__":

    # Prueba local
    import os
    download_tickets_excel("saul.alvarado", os.environ.get('PASS_SIG', ''), "Centro Cívico Gubernamental de Honduras")
