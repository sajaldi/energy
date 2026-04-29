import BAC0
import asyncio

async def verify_new_list():
    print("[TEST] Verificando dispositivo de la nueva lista...")
    ip_local = "10.21.1.132/24"
    # Datos de la primera fila de tu tabla
    target_ip = "10.40.75.30"
    target_id = 16000
    
    try:
        bacnet = BAC0.lite(ip=ip_local)
        print(f"[CHECK] Intentando leer {target_ip} (ID {target_id})...")
        address = f"{target_ip} device {target_id} objectName"
        result = await asyncio.wait_for(bacnet.read(address), timeout=3.0)
        print(f"✅ ¡EXITO! Dispositivo confirmado: {result}")
        bacnet.disconnect()
    except Exception as e:
        print(f"❌ Fallo: {e}")

if __name__ == "__main__":
    asyncio.run(verify_new_list())
