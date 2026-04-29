import BAC0
import asyncio

async def read_detailed_v3():
    print("[SCHEDULE] Extrayendo eventos del Horario de Piso 1 (Instancia 2)...")
    ip_local = "10.21.1.132/24"
    target_ip = "10.40.50.47"
    
    try:
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress="10.40.193.100", bbmdTTL=60)
        await asyncio.sleep(1)
        
        inst = 2
        name = await asyncio.wait_for(bacnet.read(f"{target_ip} schedule {inst} objectName"), timeout=2.0)
        print(f"\nHORARIO: {name}")
        
        weekly = await asyncio.wait_for(bacnet.read(f"{target_ip} schedule {inst} weeklySchedule"), timeout=5.0)
        days = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
        
        for i, daily_obj in enumerate(weekly):
            print(f"  {days[i]}:")
            events = daily_obj.daySchedule
            if not events:
                print("    (Sin eventos)")
                continue
            for event in events:
                # v3 de bacpypes usa objetos TimeValue
                t = event.time
                v = event.value
                # Imprimimos representacion cruda de t y v
                print(f"    - Hora: {t} -> Valor: {v}")

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(read_detailed_v3())
