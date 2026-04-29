import BAC0
import asyncio
import time

async def verify_table():
    print("[SCAN] Verificando alcance de la tabla de dispositivos...")
    ip_local = "10.21.1.132/24"
    
    # Datos extraidos de tu captura
    devices_to_test = [
        {'ip': '10.40.50.47', 'id': 11000, 'name': 'T2-N1-ILUMINACION-UPS'},
        {'ip': '10.40.75.30', 'id': 16000, 'name': 'VENTILACION-S0'},
        {'ip': '10.40.75.33', 'id': 100000, 'name': 'CUARTO-DE-BOMBA'},
        {'ip': '10.40.75.32', 'id': 18000, 'name': 'VENTILACION-S3-S4-F2'},
        {'ip': '10.40.102.26', 'id': 15000, 'name': 'CBC-PB-ILUMINACION-UPS'},
        {'ip': '10.40.100.25', 'id': 2000, 'name': 'CBA-PB-SUBESTACION'},
        {'ip': '10.40.20.26', 'id': 25000, 'name': 'T1-N1-ILUMINACION-UPS'},
        {'ip': '10.40.101.26', 'id': 9000, 'name': 'CBB-PB-SUBESTACION'},
        {'ip': '10.40.20.27', 'id': 26000, 'name': 'T1-N1-SUBESTACION'},
        {'ip': '10.40.20.21', 'id': 23000, 'name': 'T1-N23-HVAC1'},
        {'ip': '10.40.20.22', 'id': 24000, 'name': 'T1-N23-HVAC2'},
    ]

    try:
        bacnet = BAC0.lite(ip=ip_local)
        results = []

        for d in devices_to_test:
            print(f"[CHECK] Probando {d['name']} ({d['ip']})... ", end="", flush=True)
            try:
                # Intentamos leer objectName para confirmar
                address = f"{d['ip']} device {d['id']} objectName"
                # Timeout corto para no esperar demasiado por los que no llegan
                name = await asyncio.wait_for(bacnet.read(address), timeout=2.5)
                print(f"OK ({name})")
                results.append(d)
            except Exception:
                print("TIMEOUT")

        print(f"\n[RESUMEN] {len(results)} de {len(devices_to_test)} dispositivos son alcanzables.")
        bacnet.disconnect()
        return results
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return []

if __name__ == "__main__":
    asyncio.run(verify_table())
