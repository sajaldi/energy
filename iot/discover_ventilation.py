import BAC0
import asyncio

async def discover_points():
    print("[DISCOVER] Explorando puntos en VENTILACION-S3-S4-F2 (10.40.75.32)...")
    ip_local = "10.21.1.132/24"
    target_ip = "10.40.75.32"
    dev_id = 18000
    
    try:
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress="10.40.193.100", bbmdTTL=60)
        await asyncio.sleep(2)
        
        # Tipos de objetos a buscar
        obj_types = ['analogInput', 'analogValue', 'binaryInput', 'binaryValue', 'multiStateValue']
        
        print(f"{'TIPO':<15} {'INST':<6} {'NOMBRE':<30} {'VALOR':<10}")
        print("-" * 65)
        
        # Escaneamos las primeras 50 instancias de cada tipo (comun en controladores de ventilacion)
        for obj_type in obj_types:
            for inst in range(1, 51):
                try:
                    # Intentar leer el nombre del objeto
                    name = await asyncio.wait_for(bacnet.read(f"{target_ip} {obj_type} {inst} objectName"), timeout=1.0)
                    if name:
                        # Si existe, leemos el valor actual
                        val = await bacnet.read(f"{target_ip} {obj_type} {inst} presentValue")
                        # Y la unidad si es analogo
                        unit = ""
                        if 'analog' in obj_type:
                            try:
                                unit = await bacnet.read(f"{target_ip} {obj_type} {inst} units")
                            except: pass
                            
                        print(f"{obj_type:<15} {inst:<6} {str(name):<30} {str(val):<10} {unit}")
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    continue

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(discover_points())
