import BAC0
import asyncio

async def read_object_list():
    print("[DISCOVER] Pidiendo Object List a VENTILACION-S3-S4-F2 (10.40.75.32)...")
    ip_local = "10.21.1.132/24"
    target_ip = "10.40.75.32"
    dev_id = 18000
    
    try:
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress="10.40.193.100", bbmdTTL=60)
        await asyncio.sleep(2)
        
        # Leer la lista de objetos
        obj_list = await asyncio.wait_for(bacnet.read(f"{target_ip} device {dev_id} objectList"), timeout=10.0)
        print(f"Encontrados {len(obj_list)} objetos.")
        
        for obj in obj_list:
            obj_type, inst = obj
            # Solo nos interesan los puntos de datos (Analog, Binary, MultiState)
            if any(x in str(obj_type) for x in ['analog', 'binary', 'multiState', 'schedule']):
                try:
                    name = await asyncio.wait_for(bacnet.read(f"{target_ip} {obj_type} {inst} objectName"), timeout=1.0)
                    val = await bacnet.read(f"{target_ip} {obj_type} {inst} presentValue")
                    print(f"- {str(obj_type)} {inst}: {name} = {val}")
                except:
                    pass

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(read_object_list())
