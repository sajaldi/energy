import BAC0
import asyncio

async def whois_target():
    print("[TEST] Buscando a ID 18000 (VENTILACION-S3-S4-F2)...")
    ip_local = "10.21.1.132/24"
    
    try:
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress="10.40.193.100", bbmdTTL=60)
        await asyncio.sleep(2)
        
        # Enviar Who-Is para el rango donde esta 18000
        # discover(networks='all', range=(low, high))
        discovered = await asyncio.wait_for(bacnet.discover(range=(18000, 18000)), timeout=5.0)
        
        if discovered:
            print(f"¡ENCONTRADO! Detalles: {discovered}")
        else:
            print("No se encontro respuesta del dispositivo 18000.")

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(whois_target())
