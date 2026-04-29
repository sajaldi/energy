import BAC0
import asyncio

async def test_specific_device():
    print("[TEST] Probando conexion al dispositivo de la captura...")
    ip_local = "10.21.1.132/24"
    target_ip = "10.40.100.21"
    target_id = 1000
    
    try:
        bacnet = BAC0.lite(ip=ip_local)
        print(f"[CHECK] Intentando leer {target_ip} (ID {target_id})...")
        address = f"{target_ip} device {target_id} objectName"
        result = await asyncio.wait_for(bacnet.read(address), timeout=5.0)
        print(f"✅ ¡EXITO! Dispositivo confirmado: {result}")
        bacnet.disconnect()
    except Exception as e:
        print(f"❌ Fallo: {e}")

if __name__ == "__main__":
    asyncio.run(test_specific_device())
