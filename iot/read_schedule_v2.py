import BAC0
import asyncio

async def read_detailed_v2():
    print("[SCHEDULE] Explorando Horario de Piso 1 (Instancia 2)...")
    ip_local = "10.21.1.132/24"
    target_ip = "10.40.50.47"
    
    try:
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress="10.40.193.100", bbmdTTL=60)
        await asyncio.sleep(1)
        
        # Probamos con el horario de piso y el de iluminacion SEDIS
        target_instances = [2, 32] 
        days = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
        
        for inst in target_instances:
            try:
                name = await asyncio.wait_for(bacnet.read(f"{target_ip} schedule {inst} objectName"), timeout=2.0)
                print("\n" + "-"*50)
                print(f"HORARIO: {name} (Instancia {inst})")
                
                # Intentamos leer weeklySchedule
                weekly = await asyncio.wait_for(bacnet.read(f"{target_ip} schedule {inst} weeklySchedule"), timeout=5.0)
                
                for i, daily_obj in enumerate(weekly):
                    print(f"  {days[i]}:")
                    events = daily_obj.daySchedule
                    if not events:
                        print("    (Sin eventos)")
                        continue
                    for event in events:
                        print(f"    - {event.time.hour:02d}:{event.time.minute:02d} -> {event.value}")

                # Tambien revisamos exceptionSchedule por si acaso
                exceptions = await asyncio.wait_for(bacnet.read(f"{target_ip} schedule {inst} exceptionSchedule"), timeout=3.0)
                if exceptions:
                    print(f"  Excepciones encontradas: {len(exceptions)}")
                else:
                    print("  Sin excepciones.")
                            
            except Exception as e:
                print(f"  [!] Error: {e}")

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(read_detailed_v2())
