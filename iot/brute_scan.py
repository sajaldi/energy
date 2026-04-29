import BAC0
import asyncio
import time

async def sweep_by_read():
    print("[SCAN] Iniciando barrido por lectura directa (Brute Force)...")
    ip_local = "10.21.1.132/24"
    base_ip = "10.40.50"
    
    # Lista de IDs probables segun tu screenshot
    probable_ids = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000, 16000, 17000, 18000, 23000, 24000, 25000]

    try:
        bacnet = BAC0.lite(ip=ip_local)
        found = []

        # Vamos a probar un rango de IPs
        for i in range(40, 60):
            target_ip = f"{base_ip}.{i}"
            print(f"[CHECK] Probando IP {target_ip}...", end="\r")
            
            # Para cada IP, probamos los IDs mas probables
            # (Normalmente el ID coincide con algo de la IP o es secuencial)
            # Probaremos primero el ID que funciono para .47 (11000) y sus vecinos
            for tid in probable_ids:
                try:
                    # Intentamos una lectura rapida con timeout corto
                    # BAC0.read suele ser muy rapido si el dispositivo responde
                    address = f"{target_ip} device {tid} objectName"
                    # Usamos un timeout manual si es posible o simplemente capturamos la excepcion
                    result = await asyncio.wait_for(bacnet.read(address), timeout=1.0)
                    
                    print(f"\n[FOUND] ¡Dispositivo encontrado en {target_ip}!")
                    print(f"      ID: {tid}")
                    print(f"      Nombre: {result}")
                    found.append({'ip': target_ip, 'id': tid, 'name': result})
                    break # Si encontramos uno en esta IP, pasamos a la siguiente IP
                except:
                    continue
        
        print(f"\n\n[RESUMEN] Se encontraron {len(found)} dispositivos.")
        for d in found:
            print(f" - {d['name']} ({d['id']}) en {d['ip']}")

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] Error en el barrido: {e}")

if __name__ == "__main__":
    asyncio.run(sweep_by_read())
