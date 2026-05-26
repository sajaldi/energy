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
def _click_clock_face(page, value, mode):
    """Hace clic en el squareMask del reloj MUI a la posición geométrica
    correcta para el valor dado. Esto genera los eventos de puntero correctos
    que MUI necesita para registrar la selección y auto-cerrar el panel.

    mode: 'hour'   -> value es 1-12 (reloj 12h)
          'minute' -> value es 0-59
          'second' -> value es 0-59
    """
    import math
    try:
        mask = page.locator("div[role='menu'].MuiPickersClock-squareMask").first
        if mask.count() == 0 or not mask.is_visible():
            print(f"[_click_clock_face] squareMask no visible para mode={mode} value={value}")
            return False
        box = mask.bounding_box()
        if not box:
            return False

        cx = box['x'] + box['width'] / 2
        cy = box['y'] + box['height'] / 2
        # Radio donde están los números (aprox 80% del radio del contenedor)
        radius = min(box['width'], box['height']) * 0.38

        if mode == 'hour':
            # Reloj 12h: hora n a ángulo (n % 12) * 30 - 90 grados
            angle_deg = (int(value) % 12) * 30 - 90
        else:
            # Minutos/segundos: valor n a ángulo n * 6 - 90 grados
            angle_deg = int(value) * 6 - 90

        angle_rad = math.radians(angle_deg)
        x = cx + radius * math.cos(angle_rad)
        y = cy + radius * math.sin(angle_rad)

        page.mouse.click(x, y)
        print(f"[_click_clock_face] Clic en squareMask mode={mode} value={value} pos=({x:.0f},{y:.0f})")
        return True
    except Exception as e:
        print(f"[_click_clock_face] Error: {e}")
        return False


def pick_mui_datetime(page, dt):
    """Navega el MUI DateTimePicker para seleccionar fecha+hora exacta.
    Usa clicks geométricos sobre el squareMask del reloj para que MUI
    reciba correctamente los eventos de puntero y auto-cierre el panel.
    """
    target_day = str(dt.day)
    target_year = str(dt.year)
    hour_val = int(dt.strftime("%I"))    # 12h sin cero leading (1-12)
    hour_str = str(hour_val)
    minute_val = dt.minute               # 0-59
    minute_str = dt.strftime("%M")
    second_val = dt.second               # 0-59
    second_str = dt.strftime("%S")
    ampm_str = dt.strftime("%p").upper()

    month_names_en = ["", "January", "February", "March", "April", "May", "June",
                      "July", "August", "September", "October", "November", "December"]
    month_names_es = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                      "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

    target_month_en = month_names_en[dt.month]
    target_month_es = month_names_es[dt.month]

    print(f"[pick_mui_datetime] Iniciando selección: {target_day}/{dt.month}/{target_year} {hour_str}:{minute_str}:{second_str} {ampm_str}")

    # ================================================================
    # === FECHA (Calendario) ===
    # ================================================================
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
        print("[pick_mui_datetime] Navegando año/mes para seleccionar el día...")
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
        try:
            page.get_by_role("button", name=target_year, exact=True).first.click()
            page.wait_for_timeout(800)
        except Exception as e:
            print(f"[pick_mui_datetime] Error seleccionando año: {e}")
        try:
            month_btn = page.get_by_role("button", name=target_month_en, exact=True)
            if month_btn.count() > 0:
                month_btn.click()
            else:
                page.get_by_role("button", name=target_month_es, exact=True).click()
            page.wait_for_timeout(500)
        except Exception as e:
            print(f"[pick_mui_datetime] Error seleccionando mes: {e}")
        try:
            page.get_by_role("button", name=target_day, exact=True).first.click()
            page.wait_for_timeout(800)
            print(f"[pick_mui_datetime] Día {target_day} seleccionado tras navegación.")
        except Exception as e:
            print(f"[pick_mui_datetime] Error crítico seleccionando día: {e}")

    # ================================================================
    # === HORA (Reloj MUI) — clicks geométricos sobre squareMask ===
    # ================================================================
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

    # --- AM/PM (primero, antes de hora/minuto/segundo) ---
    try:
        ampm_btn = page.get_by_role("button", name=ampm_str)
        if ampm_btn.count() > 0 and ampm_btn.is_visible():
            ampm_btn.click()
            print(f"[pick_mui_datetime] {ampm_str} seleccionado.")
            page.wait_for_timeout(500)
        else:
            print(f"[pick_mui_datetime] Botón {ampm_str} no visible.")
    except Exception as e:
        print(f"[pick_mui_datetime] Error seleccionando AM/PM: {e}")

    # --- Hora (squareMask geométrico) ---
    try:
        if not _click_clock_face(page, hour_val, 'hour'):
            # Fallback a texto con force
            page.get_by_text(hour_str, exact=True).first.click(force=True)
            print(f"[pick_mui_datetime] Hora {hour_str} seleccionada por texto (fallback).")
        else:
            print(f"[pick_mui_datetime] Hora {hour_str} seleccionada por squareMask.")
        page.wait_for_timeout(600)
    except Exception as e:
        print(f"[pick_mui_datetime] Error seleccionando hora: {e}")

    # --- Minuto (squareMask geométrico) ---
    try:
        if not _click_clock_face(page, minute_val, 'minute'):
            page.get_by_text(minute_str, exact=True).first.click(force=True)
            print(f"[pick_mui_datetime] Minuto {minute_str} seleccionado por texto (fallback).")
        else:
            print(f"[pick_mui_datetime] Minuto {minute_str} seleccionado por squareMask.")
        page.wait_for_timeout(600)
    except Exception as e:
        print(f"[pick_mui_datetime] Error seleccionando minuto: {e}")

    # --- Segundos (squareMask geométrico — el clic correcto auto-cierra el popover) ---
    try:
        print(f"[pick_mui_datetime] Seleccionando segundos: {second_str}")
        if not _click_clock_face(page, second_val, 'second'):
            page.get_by_text(second_str, exact=True).first.click(force=True)
            print(f"[pick_mui_datetime] Segundo {second_str} seleccionado por texto (fallback).")
        else:
            print(f"[pick_mui_datetime] Segundo {second_str} seleccionado por squareMask. Popover se cierra automáticamente.")
        page.wait_for_timeout(800)
    except Exception as e:
        print(f"[pick_mui_datetime] Error seleccionando segundos: {e}")


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


def sync_individual_ticket(username, password, company_name, ticket_folio, fecha_solicitud, diagnostico_django, actividades_django, observaciones_django, observaciones_usuario_django, fecha_observaciones_usuario, fecha_cierre, evidencias=None, solicitud_adicional=False):
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
            # Logger interno que acumula los logs
            robot_logs = []
            def robot_log(msg):
                robot_logs.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
                print(msg)

            robot_log(f"Sincronizando ticket {ticket_folio}...")
            secciones_fallidas = []

            # ========== 1. LOGIN ==========
            robot_log("Paso 1: Login...")
            page.goto("https://sig.gia.mx/webapp/seguridad/entrar")
            page.wait_for_selector("#usaurio", timeout=30000)
            page.get_by_role("textbox", name="Usuario...").fill(username)
            page.get_by_role("textbox", name="Contraseña...").fill(password)
            page.locator("#select-simpleSelect").click()
            time.sleep(0.5)
            page.get_by_text(company_name).first.click()
            page.get_by_role("button", name="INGRESAR").click()
            page.wait_for_selector("text=Solicitudes", timeout=60000)
            robot_log("Login exitoso.")
            take_screenshot(page, "01_login_exitoso")

            # ========== 2. NAVEGAR A SSA ==========
            robot_log("Paso 2: Navegando a SSA...")
            try:
                page.get_by_role("link", name="Solicitudes").click()
            except Exception:
                page.get_by_text("Solicitudes").first.click()
            time.sleep(3)
            
            try:
                page.get_by_role("link", name="SSA Seguimiento de solicitud").click()
            except Exception:
                robot_log("Link SSA no encontrado, intentando con texto...")
                page.get_by_text("Seguimiento de solicitud").first.click()
            page.wait_for_selector("input.MuiSwitch-input", timeout=60000)
            robot_log("Navegado a SSA Seguimiento.")

            # ========== 3. BÚSQUEDA AVANZADA ==========
            page.locator("input.MuiSwitch-input").click()
            time.sleep(3)
            robot_log("Búsqueda avanzada activada.")

            # ========== 4. CONFIGURAR FILTROS ==========
            robot_log("Buscando el campo de búsqueda avanzada...")
            try:
                search_input = page.locator("#busqueda")
                if search_input.count() == 0:
                    search_input = page.get_by_role("textbox", name="Busqueda avanzada").first
                
                search_input.click()
                search_input.fill(ticket_folio)
                robot_log(f"Búsqueda avanzada filtrada por folio: {ticket_folio}")
            except Exception as e:
                robot_log(f"No se pudo escribir en el campo de búsqueda avanzada: {e}")
            
            take_screenshot(page, "02_busqueda_aplicada")

            try:
                page.get_by_role("button", name="Aplicar filtros").click()
            except Exception:
                page.locator("id=btnBuscar").click()
            robot_log("Filtros aplicados. Esperando carga de tabla...")
            time.sleep(3)

            # ========== 5. ESPERAR TABLA Y CLIC OJITO ==========
            row_selector = f"tr:has(td:text('{ticket_folio}'))"
            try:
                page.wait_for_selector(row_selector, timeout=120000, state="visible")
                robot_log(f"Ticket {ticket_folio} encontrado en la tabla.")
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
                    robot_log("Ojito clickeado por title.")
                elif ojito_icon.count() > 0:
                    ojito_icon.locator("xpath=..").click()
                    robot_log("Ojito clickeado por icono.")
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
                robot_log(f"Accediendo a captura de {nombre_seccion}...")
                try:
                    btn = page.get_by_role("button", name="Capturar").nth(indice)
                    if btn.count() > 0:
                        btn.click()
                        robot_log(f"Botón CAPTURAR ({nombre_seccion}) clickeado.")
                        time.sleep(3)

                        textarea = page.locator("textarea").first
                        if textarea.count() > 0:
                            textarea.click()
                            textarea.fill(str(texto or ".")[:500])
                            robot_log(f"Texto ingresado en {nombre_seccion}: {(str(texto or '')[:60])}...")
                            time.sleep(1)

                            page.get_by_role("button", name="Aplicar").first.click()
                            robot_log(f"Clic en APLICAR ({nombre_seccion}) realizado.")
                            time.sleep(3)
                            take_screenshot(page, f"04_captura_{nombre_seccion}_exitosa")
                        else:
                            robot_log(f"No se encontró textarea en modal de {nombre_seccion}.")
                            secciones_fallidas.append(nombre_seccion)
                    else:
                        robot_log(f"No se encontró botón CAPTURAR #{indice} ({nombre_seccion}).")
                        secciones_fallidas.append(nombre_seccion)
                except Exception as e:
                    robot_log(f"Error en captura de {nombre_seccion}: {e}")
                    secciones_fallidas.append(nombre_seccion)

            # ========== SOLICITUD ADICIONAL ==========
            if solicitud_adicional:
                robot_log("Solicitud Adicional marcada — aplicando campo en SIG...")
                try:
                    page.get_by_role("button", name="Modificar").first.click()
                    page.wait_for_timeout(1000)
                    page.get_by_role("textbox", name="Filtrar").fill("solicitud adicional")
                    page.wait_for_timeout(500)
                    page.get_by_role("gridcell", name="SOLICITUD ADICIONAL", exact=True).dblclick()
                    page.wait_for_timeout(1500)
                    robot_log("Campo 'Solicitud Adicional' aplicado en SIG.")
                except Exception as e:
                    robot_log(f"Error al marcar Solicitud Adicional en SIG: {e}")
                    secciones_fallidas.append("Solicitud Adicional")

            capturar_seccion(page, 0, diagnostico_django, "Diagnóstico")
            capturar_seccion(page, 1, actividades_django, "Actividades")
            capturar_seccion(page, 2, observaciones_django, "Observaciones")

            # ========== 7. ASIGNAR / CERRO (MODAL CIERRE) ==========
            if fecha_cierre:
                robot_log("Accediendo a Asignar/Cierre...")
                try:
                    # Abrir el modal "Cerro" (4to botón Asignar)
                    page.get_by_role("button", name="Asignar").nth(3).click(timeout=60000)
                    time.sleep(2.5)
                    take_screenshot(page, "05_modal_cierre_abierto")

                    fecha_local_cierre = fecha_cierre.astimezone(tz_honduras)
                    
                    # Rellenado 100% visual mediante el calendario y reloj de MUI.
                    # No intentamos escribir directamente ya que no son elementos del tipo input interactivos.
                    pick_mui_datetime(page, fecha_local_cierre)
                    time.sleep(1.5)

                    # Antes de abrir el catálogo, cerrar cualquier SweetAlert que esté bloqueando
                    try:
                        swal_blocking = page.locator(".swal2-container")
                        if swal_blocking.count() > 0 and swal_blocking.is_visible():
                            page.locator(".swal2-confirm, .swal2-close, button:has-text('OK')").first.click()
                            robot_log("[Asignar/Cierre] SweetAlert descartado antes de abrir catálogo.")
                            page.wait_for_timeout(1000)
                    except Exception:
                        pass

                    # Abrir el buscador de responsable (el botón lupa está dentro del combobox)
                    robot_log("Abriendo el buscador de responsable...")
                    page.get_by_role("combobox").get_by_role("button").click()

                    # Esperar explícitamente a que aparezca el diálogo del catálogo
                    try:
                        page.wait_for_selector("text=Catálogo de responsables", timeout=10000)
                        robot_log("[Asignar/Cierre] Diálogo 'Catálogo de responsables' abierto.")
                    except Exception:
                        robot_log("[Asignar/Cierre] ADVERTENCIA: No se confirmó apertura de catálogo, continuando...")
                    page.wait_for_timeout(800)

                    # Filtrar responsable — usar get_by_placeholder como selector primario
                    robot_log("Filtrando por 'oscar'...")
                    filtrar_loc = None
                    for loc_fn in [
                        lambda: page.get_by_placeholder("Filtrar"),
                        lambda: page.get_by_placeholder("filtrar"),
                        lambda: page.get_by_role("textbox", name="Filtrar"),
                        lambda: page.locator("input[placeholder*='iltrar']"),
                        lambda: page.locator(".MuiDialogContent-root input, .MuiPaper-root input").first,
                    ]:
                        try:
                            loc = loc_fn()
                            if loc.count() > 0 and loc.is_visible():
                                filtrar_loc = loc
                                break
                        except Exception:
                            continue

                    if filtrar_loc:
                        filtrar_loc.fill("oscar")
                        robot_log("[Asignar/Cierre] Campo 'Filtrar' llenado con 'oscar'.")
                    else:
                        # Último fallback: escribir en cualquier input visible dentro del diálogo
                        page.keyboard.type("oscar")
                        robot_log("[Asignar/Cierre] Filtrar llenado vía keyboard (fallback).")
                    page.wait_for_timeout(1500)

                    # Doble clic en Oscar Posadas Mendieta para seleccionarlo y cerrar el catálogo automáticamente
                    page.get_by_role("gridcell", name="Oscar Posadas Mendieta").dblclick()
                    page.wait_for_timeout(1000)

                    take_screenshot(page, "06_modal_cierre_llenado")

                    # Click en Aplicar para guardar y cerrar modal
                    page.get_by_role("button", name="Aplicar").click()
                    robot_log(f"Asignar/Cierre guardado: {fecha_local_cierre.strftime('%d/%m/%Y %I:%M %p')} - Oscar Posadas Mendieta")
                    time.sleep(3)

                    # Manejar cualquier SweetAlert de confirmación o advertencia que aparezca
                    try:
                        swal_title = page.locator("#swal2-title")
                        swal_content = page.locator("#swal2-content, .swal2-html-container")
                        if swal_title.count() > 0 and swal_title.is_visible():
                            title_text = swal_title.inner_text()
                            content_text = swal_content.inner_text() if swal_content.count() > 0 else ""
                            robot_log(f"[Asignar/Cierre] [SWEETALERT] {title_text}: {content_text}")
                            
                            confirm_btn = page.locator(".swal2-confirm, button:has-text('OK'), button:has-text('Aceptar'), button:has-text('Entendido')").first
                            if confirm_btn.count() > 0:
                                confirm_btn.click()
                                robot_log("[Asignar/Cierre] Diálogo SweetAlert descartado.")
                                time.sleep(1.5)
                    except Exception as e_swal:
                        robot_log(f"[Asignar/Cierre] No se pudo procesar SweetAlert pop-up: {e_swal}")

                except Exception as e:
                    robot_log(f"Error en fase de Asignar/Cierre: {e}")
                    secciones_fallidas.append("Asignar/Cierre")
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
                        robot_log(f"No se pudo hacer clic en Salir para cerrar modal: {e_salir}")
                    time.sleep(1.5)
            else:
                robot_log("fecha_cierre no proporcionada, saltando Asignar/Cierre.")

            # ========== 8. ADJUNTOS (EVIDENCIAS) ==========
            # NO presionar Escape aquí: eso cierra el panel del ticket y vuelve a la tabla
            time.sleep(1)
            take_screenshot(page, "07_antes_adjuntos")
            
            # Subir evidencias con logs acumulativos
            if evidencias:
                for i, ev in enumerate(evidencias):
                    robot_log(f"Subiendo evidencia {i+1}/{len(evidencias)}: {ev['descripcion'][:60]}...")
                    try:
                        # 1. Llenar descripción del adjunto
                        desc = page.locator("#adjDescripcion")
                        desc.scroll_into_view_if_needed(timeout=15000)
                        desc.click()
                        desc.fill(ev['descripcion'])
                        time.sleep(1.0)
                        
                        # 2. Cargar el archivo usando el file chooser al hacer click en el botón Agregar
                        robot_log("Esperando botón Agregar...")
                        agregar_btn = page.locator("span#confirmar, button:has-text('Agregar'), [label='Agregar']").first
                        agregar_btn.scroll_into_view_if_needed(timeout=10000)
                        
                        # Usar expect_file_chooser para interceptar el diálogo de archivos
                        with page.expect_file_chooser() as fc_info:
                            agregar_btn.click()
                        
                        file_chooser = fc_info.value
                        file_chooser.set_files(ev['path'])
                        robot_log(f"Evidencia {i+1} cargada mediante file chooser.")
                        time.sleep(3.0)
                        
                    except Exception as e:
                        robot_log(f"Error en evidencia {i+1}: {e}")
                        # Intentar fallback directo
                        try:
                            robot_log("Intentando fallback directo a input[type='file']...")
                            input_file = page.locator("input[type='file']").first
                            if input_file.count() > 0:
                                input_file.set_input_files(ev['path'])
                                robot_log("Evidencia subida exitosamente vía input[type='file'] fallback.")
                                time.sleep(3.0)
                            else:
                                raise Exception("No se encontró input[type='file']")
                        except Exception as e_fallback:
                            robot_log(f"Fallback también falló: {e_fallback}")
                            secciones_fallidas.append(f"Evidencia {i+1}: {ev['descripcion']}")
                            page.screenshot(path=os.path.join(settings.BASE_DIR, "downloads", f"error_adjuntos_{i+1}.png"))

            # ========== 9. FINALIZAR ==========
            screenshot_path = os.path.join(settings.BASE_DIR, "downloads", f"final_sync_{ticket_folio}.png")
            page.screenshot(path=screenshot_path)
            browser.close()

            # Evaluar estatus de automatización
            if secciones_fallidas:
                estatus = "TICKET INCOMPLETO"
                msg = f"Sincronización parcial. Fallas detectadas en: {', '.join(secciones_fallidas)}."
            else:
                estatus = "TICKET COMPLETAMENTE DOCUMENTADO"
                msg = "Sincronización totalmente exitosa sin fallas."

            return {
                "status": "success", 
                "robot_estatus": estatus,
                "message": msg, 
                "screenshot": screenshot_path,
                "robot_log": "\n".join(robot_logs)
            }

        except Exception as e:
            error_screenshot = os.path.join(settings.BASE_DIR, "downloads", f"error_robot_{ticket_folio}.png")
            robot_log(f"Error crítico en el robot: {e}")
            page.screenshot(path=error_screenshot)
            browser.close()
            return {
                "status": "error", 
                "robot_estatus": "TICKET INCOMPLETO",
                "message": str(e), 
                "screenshot": error_screenshot,
                "robot_log": "\n".join(robot_logs)
            }

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
