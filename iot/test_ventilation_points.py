import BAC0
import asyncio

async def test_common_points():
    print("[TEST] Probando puntos comunes en VENTILACION-S3-S4-F2 (10.40.75.32)...")
    ip_local = "10.21.1.132/24"
    target_ip = "10.40.75.32"
    
    try:
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress="10.40.193.100", bbmdTTL=60)
        await asyncio.sleep(2)
        
        # Lista de sospechosos comunes
        tests = [
            ('binaryValue', 1, 'Estado Fan'),
            ('analogValue', 1, 'Velocidad/Freq'),
            ('analogInput', 1, 'Sensor'),
            ('binaryInput', 1, 'Fallo/Alarma')
        ]
        
        for obj_type, inst, label in tests:
            try:
                name = await asyncio.wait_for(bacnet.read(f"{target_ip} {obj_type} {inst} objectName"), timeout=2.0)
                val = await bacnet.read(f"{target_ip} {obj_type} {inst} presentValue")
                print(f"MATCH: {label} ({obj_type} {inst}) -> {name} = {val}")
            except Exception as e:
                print(f"MISS: {label} ({obj_type} {inst}) -> No responde")

        bacnet.disconnect()
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(test_common_points())
