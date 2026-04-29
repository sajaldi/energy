import BAC0
import asyncio
import time

async def foreign_device_discovery():
    print("[SCAN] Iniciando descubrimiento via BBMD Registration en 10.40.50.47...")
    ip_local = "10.21.1.132/24"
    router_ip = "10.40.50.47"
    
    try:
        # En BAC0 Lite (bacpypes3), el registro se pasa en el constructor
        print(f"[REGISTER] Inicializando con BBMD: {router_ip}")
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress=router_ip, bbmdTTL=60)
        
        # Esperamos a que se establezca la sesion
        await asyncio.sleep(5)
        
        print("[SCAN] Enviando WhoIs global...")
        await bacnet.who_is()
        
        print("[WAIT] Esperando 15s por respuestas...")
        start_wait = time.time()
        while time.time() - start_wait < 15:
            await asyncio.sleep(3)
            devices = bacnet.devices
            if asyncio.iscoroutine(devices): devices = await devices
            count = len(devices) if devices else 0
            print(f"[STATUS] {count} dispositivos encontrados...")

        final_devices = bacnet.devices
        if asyncio.iscoroutine(final_devices): final_devices = await final_devices
        
        if final_devices:
            print(f"\n[SUCCESS] ¡Listado encontrado!")
            for d in final_devices:
                if isinstance(d, tuple):
                    print(f" - {d[0]} (ID: {d[1]}) en {d[2]}")
                else:
                    print(f" - {getattr(d, 'name', '?')} (ID: {getattr(d, 'device_id', '?')}) en {getattr(d, 'address', '?')}")
        else:
            print("\n[FAIL] No se descubrieron dispositivos. Es posible que el router no acepte registros de dispositivos extranjeros.")

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(foreign_device_discovery())
