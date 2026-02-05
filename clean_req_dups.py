from presupuestos.models import Requisicion
from django.db.models import Count

dups = Requisicion.objects.values('cr8ca_requisicion').annotate(count=Count('cr8ca_requisicion')).filter(count__gt=1)

for d in dups:
    val = d['cr8ca_requisicion']
    reqs = Requisicion.objects.filter(cr8ca_requisicion=val).order_by('cr8ca_requisicionid')
    print(f"Resolving {len(reqs)} duplicates for {val}")
    for i, r in enumerate(reqs[1:], 1):
        old_val = r.cr8ca_requisicion
        new_val = f"{old_val}-DUP{i}"
        r.cr8ca_requisicion = new_val
        r.save()
        print(f"  Renamed {old_val} -> {new_val}")
