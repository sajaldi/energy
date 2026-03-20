import os
import django
import sys

# Setup Django environment
sys.path.append(r'd:\Apps\energia\energy')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from callcenter.models import SolicitudTicket, EvidenciaTicket

log_path = r'd:\Apps\energia\energy\tmp\debug_log.txt'

with open(log_path, 'w', encoding='utf-8') as f:
    def log(msg):
        print(msg)
        f.write(msg + '\n')

    folio = 'SS26-139237'
    t = SolicitudTicket.objects.filter(folio=folio).first()

    if t:
        log(f"Ticket Found: {t.folio} (ID: {t.id_solicitud})")
        log(f"Fecha Cierre: {t.fecha_cierre}")
        evs = t.evidencias.all()
        log(f"Total Evidencias: {evs.count()}")
        for e in evs:
            log(f" - Desc: {e.descripcion}")
            log(f"   Archivo: {e.archivo.name if e.archivo else 'No file'}")
            if e.archivo:
                try:
                    log(f"   Size: {e.archivo.size} bytes")
                    exists = e.archivo.storage.exists(e.archivo.name)
                    log(f"   Exists in storage: {exists}")
                except Exception as ex:
                    log(f"   Error checking storage: {ex}")
    else:
        log(f"Ticket {folio} not found in database.")
