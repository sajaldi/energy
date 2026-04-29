import BAC0
import asyncio
import time

async def test_direct_read():
    print("[TEST] Iniciando prueba de comunicacion directa...")
    # IP local en la VPN
    ip_local = "10.21.1.132/24"
    target_ip = "10.40.50.47"
    target_id = 11000

    try:
        bacnet = BAC0.lite(ip=ip_local)
        print(f"[TEST] Conectando directamente a {target_ip} (ID {target_id})...")
        
        # Formato de lectura para BAC0
        # address device_id property
        address = f"{target_ip} device {target_id} objectName"
        print(f"[TEST] Leyendo: {address}")
        
        try:
            # En BAC0 Lite (bacpypes3), read es async
            result = await bacnet.read(address)
            print(f"[OK] ¡EXITO! Nombre del dispositivo: {result}")
        except Exception as e:
            print(f"[ERROR] Error al leer: {e}")

        bacnet.disconnect()
    except Exception as e:
        print(f"[CRITICAL] Error critico: {e}")

if __name__ == "__main__":
    asyncio.run(test_direct_read())
