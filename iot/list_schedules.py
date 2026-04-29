import BAC0
import asyncio

async def list_schedule_names():
    print("[SCHEDULE] Listando nombres de horarios en 10.40.50.47...")
    ip_local = "10.21.1.132/24"
    target_ip = "10.40.50.47"
    target_id = 11000
    
    try:
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress="10.40.193.100", bbmdTTL=60)
        address_list = f"{target_ip} device {target_id} objectList"
        obj_list = await asyncio.wait_for(bacnet.read(address_list), timeout=10.0)
        
        schedules = [obj for obj in obj_list if str(obj[0]) == 'schedule']
        
        for s_type, s_inst in schedules:
            try:
                name = await asyncio.wait_for(bacnet.read(f"{target_ip} schedule {s_inst} objectName"), timeout=1.2)
                val = await asyncio.wait_for(bacnet.read(f"{target_ip} schedule {s_inst} presentValue"), timeout=1.2)
                print(f"  [{s_inst}] {name} = {'ON' if val else 'OFF'}")
            except Exception as e:
                # print(f"  [{s_inst}] Error: {e}")
                continue

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(list_schedule_names())
