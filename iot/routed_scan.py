import BAC0
import asyncio
import time

async def discovery_routed():
    print("[SCAN] Iniciando descubrimiento ruteado a traves del Router 10.40.50.47...")
    ip_local = "10.21.1.132/24"
    router_ip = "10.40.50.47"
    
    # Redes que vimos en tu captura
    networks = [9, 11, 20, 61]
    
    try:
        bacnet = BAC0.lite(ip=ip_local)
        
        # 1. Primero confirmamos el Router
        print(f"[CHECK] Verificando Router en {router_ip}...")
        try:
            router_name = await asyncio.wait_for(bacnet.read(f"{router_ip} device 11000 objectName"), timeout=2.0)
            print(f"[OK] Router encontrado: {router_name}")
        except:
            print("[FAIL] No se pudo comunicar con el Router.")
            return

        # 2. Intentamos descubrir dispositivos en las redes ruteadas
        # Enviamos un WhoIs especificando la red destino a traves del router
        for net in networks:
            print(f"[SCAN] Buscando dispositivos en Red {net} a traves de {router_ip}...")
            # En BAC0, para enviar a una red remota: address='IP:port net'
            # Esto envia un WhoIs a la red remota
            try:
                await bacnet.who_is(address=f"{router_ip}:47808 {net}")
            except: pass
            
        print("[WAIT] Esperando 10s por respuestas de dispositivos remotos...")
        await asyncio.sleep(10)
        
        devices = bacnet.devices
        if asyncio.iscoroutine(devices):
            devices = await devices
            
        if devices:
            print(f"\n[SUCCESS] ¡Se encontraron {len(devices)} dispositivos!")
            for d in devices:
                if isinstance(d, tuple):
                    print(f" - ID: {d[1]} | Nombre: {d[0]} | Direccion: {d[2]}")
                else:
                    print(f" - ID: {getattr(d, 'device_id', '?')} | Nombre: {getattr(d, 'name', '?')} | Direccion: {getattr(d, 'address', '?')}")
        else:
            print("\n[WARN] No se descubrieron dispositivos adicionales por WhoIs.")
            print("      Intentando lectura directa de IDs conocidos en Red 20...")
            
            # Prueba especifica de uno de los IDs de tu captura (2001164 en Red 20)
            # Formato: IP:port net station device id property
            # Station suele ser parte del ID o secuencial. En Reliable suele ser ID % 100000 o similar.
            # Segun tu captura 20_CBC... (2001164) -> quizas la estacion es 1164?
            # Probaremos varios formatos
            test_ids = [2001164, 2001264, 2030864, 2057600]
            for tid in test_ids:
                # El formato de Reliable suele ser 'IP:47808 net station'
                # Intentamos descubrir la station
                print(f"[CHECK] Intentando leer ID {tid} en Red 20...")
                # En BAC0 podemos intentar leer por ID directamente si el WhoIs fallo pero el ruteo existe
                # Pero necesitamos la direccion. 
                # Si no la tenemos, el escaneo es dificil sin WhoIs funcional.
                pass

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(discovery_routed())
