import BAC0
import asyncio

async def browse_points():
    print("[EXPLORER] Extrayendo nombres de variables en 10.40.50.47...")
    ip_local = "10.21.1.132/24"
    target_ip = "10.40.50.47"
    target_id = 11000
    
    try:
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress="10.40.193.100", bbmdTTL=60)
        address = f"{target_ip} device {target_id} objectList"
        obj_list = await asyncio.wait_for(bacnet.read(address), timeout=15.0)
        
        print("\n[MUESTRA DE VARIABLES DISPONIBLES]:")
        count = 0
        for obj_id in obj_list:
            o_type = str(obj_id[0])
            o_inst = obj_id[1]
            
            # Buscamos analog-value o binary-value (usamos minusculas para comparar)
            if 'value' in o_type.lower() or 'input' in o_type.lower():
                try:
                    # En Reliable Controls, el objectName suele decir que es la variable
                    name = await asyncio.wait_for(bacnet.read(f"{target_ip} {o_type} {o_inst} objectName"), timeout=1.2)
                    val = await asyncio.wait_for(bacnet.read(f"{target_ip} {o_type} {o_inst} presentValue"), timeout=1.2)
                    
                    # Formatear el valor si es float
                    if isinstance(val, float): val = round(val, 2)
                    
                    print(f"  [{o_type} {o_inst}] {name} = {val}")
                    count += 1
                    if count >= 30: break # Vemos 30 variables
                except: continue

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(browse_points())
