import BAC0
import asyncio

async def test_hop_via_bbmd():
    print("[TEST] Usando 10.40.193.100 como BBMD...")
    ip_local = "10.21.1.132/24"
    bbmd_ip = "10.40.193.100"
    
    try:
        bacnet = BAC0.lite(ip=ip_local, bbmdAddress=bbmd_ip, bbmdTTL=60)
        print(f"[REGISTER] Registrado en BBMD {bbmd_ip}")
        await asyncio.sleep(2)
        
        # 1. Probar el que ya sabemos que responde
        print(f"[CHECK 1] Probando 10.40.50.47 (ID 11000)...")
        res1 = await asyncio.wait_for(bacnet.read("10.40.50.47 device 11000 objectName"), timeout=5.0)
        print(f"[OK] Responde: {res1}")
        
        # 2. Probar el de la captura (10.40.100.21 ID 1000)
        print(f"[CHECK 2] Probando 10.40.100.21 (ID 1000)...")
        res2 = await asyncio.wait_for(bacnet.read("10.40.100.21 device 1000 objectName"), timeout=5.0)
        print(f"[OK] Responde: {res2}")

        bacnet.disconnect()
        print("\n[CONCLUSION] ¡El puente BBMD funciona perfectamente!")
    except Exception as e:
        print(f"\n[ERROR] Error en el puente: {e}")

if __name__ == "__main__":
    asyncio.run(test_hop_via_bbmd())
