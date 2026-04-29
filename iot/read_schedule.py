import BAC0
import asyncio
from bacpypes3.basetypes import DailySchedule

async def read_schedules():
    print("[SCHEDULE] Buscando programas de horario en T2-N1-ILUMINACION-UPS...")
    ip_local = "10.21.1.132/24"
    target_ip = "10.40.50.47"
    target_id = 11000
    
    try:
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress="10.40.193.100", bbmdTTL=60)
        
        # 1. Obtener lista de objetos para filtrar los schedules
        address_list = f"{target_ip} device {target_id} objectList"
        obj_list = await asyncio.wait_for(bacnet.read(address_list), timeout=10.0)
        
        schedules = [obj for obj in obj_list if str(obj[0]) == 'schedule']
        print(f"[INFO] Encontrados {len(schedules)} objetos de horario.")

        for s_type, s_inst in schedules:
            try:
                # Leer nombre del horario
                name = await asyncio.wait_for(bacnet.read(f"{target_ip} schedule {s_inst} objectName"), timeout=1.5)
                # Leer el horario semanal
                weekly = await asyncio.wait_for(bacnet.read(f"{target_ip} schedule {s_inst} weeklySchedule"), timeout=2.0)
                # Leer el valor actual del horario
                current = await asyncio.wait_for(bacnet.read(f"{target_ip} schedule {s_inst} presentValue"), timeout=1.5)
                
                print(f"\n------------------------------------------------")
                print(f"📅 HORARIO: {name} (Instancia {s_inst})")
                print(f"   Estado Actual: {'ON' if current else 'OFF'} ({current})")
                
                # Mostrar un resumen del horario semanal (Lunes a Domingo)
                days = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
                for i, day_name in enumerate(days):
                    day_schedule = weekly[i]
                    if day_schedule and len(day_schedule) > 0:
                        events = []
                        for event in day_schedule:
                            # event.time y event.value
                            t = event.time
                            v = event.value
                            events.append(f"{t.hour:02d}:{t.minute:02d} -> {v}")
                        print(f"   - {day_name}: {' | '.join(events)}")
                    else:
                        print(f"   - {day_name}: (Sin eventos)")
                        
            except Exception as e:
                # print(f"   [!] Error leyendo horario {s_inst}: {e}")
                continue

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(read_schedules())
