import os
import time
from playwright.sync_api import sync_playwright

def test_scraper():
    username = os.environ.get('CALLCENTER_USER', 'saul.alvarado')
    password = os.environ.get('PASS_SIG', '')
    company_name = "Centro Cívico Gubernamental de Honduras"

    if not password:
        print("ERROR: PASS_SIG no está definida.")
        return

    print(f"Password length: {len(password)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(60000)

        os.makedirs("downloads", exist_ok=True)

        try:
            print("1. Navegando a SIG GIA...")
            page.goto("https://sig.gia.mx/webapp/seguridad/entrar", wait_until="networkidle", timeout=60000)
            page.screenshot(path="downloads/step1_login_page.png")
            print("   Página de login cargada.")

            print("2. Llenando credenciales...")
            page.fill("input#usaurio", username)
            page.fill("input#combinacion", password)
            
            print("3. Seleccionando empresa...")
            page.click("div#select-simpleSelect")
            time.sleep(1)
            page.click(f"li[role='option']:has-text('{company_name}')")
            
            print("4. Haciendo clic en INGRESAR...")
            page.click("button:has-text('INGRESAR')")
            
            print("5. Esperando que cargue el dashboard...")
            time.sleep(5)
            page.screenshot(path="downloads/step2_after_login.png")
            
            # Verificar si hay error de login
            error_modal = page.locator("text=Usuario o contraseña incorrecta")
            if error_modal.count() > 0:
                print("ERROR: Usuario o contraseña incorrecta!")
                browser.close()
                return

            print("   Login parece exitoso, buscando menú Solicitudes...")
            try:
                page.wait_for_selector("text=Solicitudes", timeout=30000)
                print("   Menú 'Solicitudes' encontrado!")
            except:
                print("   No se encontró 'Solicitudes'. Revisando screenshot...")
                page.screenshot(path="downloads/step3_no_solicitudes.png")
                # Imprimir el HTML del body para ver qué hay en pantalla
                body_text = page.locator("body").inner_text()
                print(f"   Body text (primeros 500 chars): {body_text[:500]}")
                browser.close()
                return

            print("6. Navegando a SSA Seguimiento...")
            page.click("text=Solicitudes")
            time.sleep(1)
            page.click("text=Seguimiento de solicitud de atención")
            
            page.wait_for_selector("input.MuiSwitch-input", timeout=60000)
            print("   Navegado a SSA Seguimiento.")
            page.screenshot(path="downloads/step4_ssa.png")

            print("7. Activando búsqueda avanzada...")
            page.click("input.MuiSwitch-input")
            time.sleep(2)
            page.screenshot(path="downloads/step5_busqueda_avanzada.png")

            # Revisar inputs
            inputs = page.locator("input.MuiInputBase-input:not([type='hidden'])").all()
            print(f"   Se encontraron {len(inputs)} inputs MuiInputBase-input")
            for i, inp in enumerate(inputs):
                is_enabled = inp.is_enabled()
                print(f"   Input {i}: enabled={is_enabled}")

            print("\n=== DEBUG COMPLETO ===")
            print("El scraper llegó hasta la búsqueda avanzada correctamente.")
            
        except Exception as e:
            print(f"ERROR: {e}")
            page.screenshot(path="downloads/step_error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    test_scraper()
