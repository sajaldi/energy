from callcenter.models import SolicitudTicket, EvidenciaTicket
import os

folio = 'SS26-139237'
print(f"Searching for folio: {folio}")
t = SolicitudTicket.objects.filter(folio=folio).first()

if not t:
    print(f"Folio {folio} NOT found. Searching by ID if numeric...")
    try:
        t = SolicitudTicket.objects.filter(id_solicitud=int(folio.split('-')[-1])).first()
    except: pass

if t:
    print(f"Ticket Found: {t.folio} (ID: {t.id_solicitud})")
    evs = t.evidencias.all()
    print(f"Evidencias Count: {evs.count()}")
    for e in evs:
        print(f" - {e.descripcion} | Archivo: {e.archivo.name if e.archivo else 'None'}")
        if e.archivo:
            try:
                exists = e.archivo.storage.exists(e.archivo.name)
                print(f"   Size: {e.archivo.size} | Exists in storage: {exists}")
                print(f"   URL: {e.archivo.url}")
            except Exception as ex:
                print(f"   Error: {ex}")
else:
    print("Ticket NOT found.")
    print("Recent Folios:")
    for rt in SolicitudTicket.objects.all().order_by('-id')[:10]:
        print(f" - {rt.folio}")
