import BAC0
import asyncio

async def broad_discover():
    print("[TEST] Iniciando descubrimiento general para encontrar ID 18000...")
    ip_local = "10.21.1.132/24"
    
    try:
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress="10.40.193.100", bbmdTTL=60)
        await asyncio.sleep(2)
        
        # Enviar Who-Is
        print("Enviando Who-Is...")
        # Probamos con await en discover por si acaso, si no es corrutina fallara pero seguiremos
        try:
            await bacnet.discover(networks='all')
        except:
            bacnet.discover(networks='all')
        
        # Esperar a que los dispositivos respondan
        await asyncio.sleep(5)
        
        # devices parece ser una corrutina segun el error anterior
        discovered = await bacnet.devices
        print(f"Se encontraron {len(discovered)} dispositivos en total.")
        
        found = False
        for dev in discovered:
            try:
                addr, dev_id = dev
                if int(dev_id) == 18000:
                    print(f"¡LO ENCONTRAMOS! IP: {addr}, ID: {dev_id}")
                    name = await asyncio.wait_for(bacnet.read(f"{addr} device {dev_id} objectName"), timeout=2.0)
                    print(f"Nombre confirmado: {name}")
                    found = True
            except:
                pass
        
        if not found:
            print("El ID 18000 no respondio.")

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(broad_discover())
