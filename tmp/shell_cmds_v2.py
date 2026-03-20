from callcenter.models import SolicitudTicket, EvidenciaTicket
import os

log_path = r'd:\Apps\energia\energy\tmp\shell_output.txt'

with open(log_path, 'w', encoding='utf-8') as f:
    def log(msg):
        print(msg)
        f.write(str(msg) + '\n')

    folio = 'SS26-139237'
    log(f"Searching for folio: {folio}")
    t = SolicitudTicket.objects.filter(folio=folio).first()

    if not t:
        log(f"Folio {folio} NOT found. Searching by ID if numeric...")
        try:
            t = SolicitudTicket.objects.filter(id_solicitud=int(folio.split('-')[-1])).first()
        except: pass

    if t:
        log(f"Ticket Found: {t.folio} (ID: {t.id_solicitud})")
        evs = t.evidencias.all()
        log(f"Evidencias Count: {evs.count()}")
        for e in evs:
            log(f" - {e.descripcion} | Archivo: {e.archivo.name if e.archivo else 'None'}")
            if e.archivo:
                try:
                    exists = e.archivo.storage.exists(e.archivo.name)
                    log(f"   Size: {e.archivo.size} | Exists in storage: {exists}")
                    log(f"   URL: {e.archivo.url}")
                except Exception as ex:
                    log(f"   Error: {ex}")
    else:
        log("Ticket NOT found.")
        log("Recent Folios:")
        for rt in SolicitudTicket.objects.all().order_by('-id')[:10]:
            log(f" - {rt.folio}")
