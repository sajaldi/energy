import BAC0
import asyncio

async def direct_test():
    print("[TEST] Tocando la puerta directamente a 10.40.75.32 (ID 18000)...")
    ip_local = "10.21.1.132/24"
    target_ip = "10.40.75.32"
    dev_id = 18000
    
    try:
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress="10.40.193.100", bbmdTTL=60)
        await asyncio.sleep(2)
        
        # Intentar leer el nombre del dispositivo usando su IP
        try:
            name = await asyncio.wait_for(bacnet.read(f"{target_ip} device {dev_id} objectName"), timeout=5.0)
            print(f"¡CONEXION EXITOSA! El equipo dice llamarse: {name}")
            
            # Si respondio, probamos leer el punto analog-value 1
            val = await bacnet.read(f"{target_ip} analogValue 1 presentValue")
            p_name = await bacnet.read(f"{target_ip} analogValue 1 objectName")
            print(f"Punto detectado: {p_name} = {val}")
        except asyncio.TimeoutError:
            print("TIMEOUT: El equipo no respondio a la IP 10.40.75.32.")
        except Exception as e:
            print(f"ERROR en lectura directa: {e}")

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(direct_test())
