import BAC0
import asyncio

async def read_schedules_robust():
    print("[SCHEDULE] Leyendo horarios detallados en 10.40.50.47...")
    ip_local = "10.21.1.132/24"
    target_ip = "10.40.50.47"
    
    try:
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress="10.40.193.100", bbmdTTL=60)
        await asyncio.sleep(1)
        
        target_instances = [34, 31, 30] 
        days = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
        
        for inst in target_instances:
            try:
                name = await asyncio.wait_for(bacnet.read(f"{target_ip} schedule {inst} objectName"), timeout=2.0)
                print("\n" + "-"*50)
                print(f"HORARIO: {name} (Instancia {inst})")
                
                weekly = await asyncio.wait_for(bacnet.read(f"{target_ip} schedule {inst} weeklySchedule"), timeout=5.0)
                
                for i, daily_obj in enumerate(weekly):
                    print(f"  {days[i]}:")
                    events = daily_obj.daySchedule
                    if not events:
                        print("    (Sin eventos)")
                        continue
                        
                    for event in events:
                        t = event.time
                        v = event.value
                        try:
                            val = v.value if hasattr(v, 'value') else v
                            status = "ON" if val == 1 else ("OFF" if val == 0 else str(val))
                            print(f"    - {t.hour:02d}:{t.minute:02d} -> {status}")
                        except:
                            print(f"    - {t.hour:02d}:{t.minute:02d} -> {v}")
                            
            except Exception as e:
                print(f"  [!] Error: {e}")

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(read_schedules_robust())
