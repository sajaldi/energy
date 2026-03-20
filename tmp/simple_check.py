from callcenter.models import SolicitudTicket, EvidenciaTicket
t = SolicitudTicket.objects.filter(folio='SS26-139237').first()
print(f"FOUND: {t != None}")
if t:
    print(f"EVIDENCIAS: {t.evidencias.count()}")
    for e in t.evidencias.all():
        print(f"  - {e.descripcion}: {e.archivo}")
else:
    print("Recent tickets:")
    for rt in SolicitudTicket.objects.all().order_by('-id')[:5]:
        print(f" - {rt.folio}")
