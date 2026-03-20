import os
import sys

# Add project root to path
PROJECT_ROOT = r'd:\Apps\energia\energy'
sys.path.append(PROJECT_ROOT)

# Set settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')

import django
try:
    django.setup()
    from callcenter.models import SolicitudTicket, EvidenciaTicket
    from django.conf import settings
    
    log_path = os.path.join(PROJECT_ROOT, 'tmp', 'debug_log_final.txt')
    
    with open(log_path, 'w', encoding='utf-8') as f:
        def log(msg):
            print(msg)
            f.write(str(msg) + '\n')

        log(f"DB Engine: {settings.DATABASES['default']['ENGINE']}")
        log(f"DB Name: {settings.DATABASES['default']['NAME']}")
        log(f"DB Host: {settings.DATABASES['default'].get('HOST')}")
        log(f"DB Port: {settings.DATABASES['default'].get('PORT')}")

        folio = 'SS26-139237'
        t = SolicitudTicket.objects.filter(folio=folio).first()

        if t:
            log(f"\nTicket Found: {t.folio} (ID: {t.id_solicitud})")
            log(f"Fecha Cierre: {t.fecha_cierre}")
            log(f"Estado de Cierre: {'Cerrado' if t.fecha_cierre else 'Abierto'}")
            
            evs = t.evidencias.all()
            log(f"Total Evidencias: {evs.count()}")
            for e in evs:
                log(f"\n - ID: {e.id}")
                log(f"   Desc: {e.descripcion}")
                log(f"   Archivo: {e.archivo.name if e.archivo else 'No file'}")
                if e.archivo:
                    try:
                        log(f"   Size: {e.archivo.size} bytes")
                        exists = e.archivo.storage.exists(e.archivo.name)
                        log(f"   Exists in storage: {exists}")
                        log(f"   URL: {e.archivo.url}")
                    except Exception as ex:
                        log(f"   Error checking storage: {ex}")
        else:
            log(f"\nTicket {folio} not found in database.")
            
            # Look for ANY recent tickets to see if the folio format changed
            recent = SolicitudTicket.objects.order_by('-id')[:5]
            log("\nRecent tickets in DB:")
            for rt in recent:
                log(f" - {rt.folio} (ID: {rt.id_solicitud})")

except Exception as e:
    import traceback
    print(f"Error during setup: {e}")
    traceback.print_exc()
