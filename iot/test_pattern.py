import BAC0
import asyncio
import time

async def test_pattern():
    print("[TEST] Probando teoria de mapeo Host <-> IP...")
    ip_local = "10.21.1.132/24"
    
    # Pruebas basadas en la teoria Host+36 = IP_last_octet
    tests = [
        {'ip': '10.40.50.37', 'id': 1000},  # Host 1
        {'ip': '10.40.50.38', 'id': 2000},  # Host 2
        {'ip': '10.40.50.47', 'id': 11000}, # Host 11 (Sabemos que este funciona)
        {'ip': '10.40.50.61', 'id': 25000}, # Host 25?
    ]
    
    try:
        bacnet = BAC0.lite(ip=ip_local)
        for t in tests:
            target_ip = t['ip']
            target_id = t['id']
            print(f"[CHECK] Intentando leer ID {target_id} en {target_ip}...")
            try:
                address = f"{target_ip} device {target_id} objectName"
                result = await asyncio.wait_for(bacnet.read(address), timeout=2.0)
                print(f"   ✅ ENCONTRADO: {result}")
            except:
                print(f"   ❌ No responde.")

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(test_pattern())
