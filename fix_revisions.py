import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from documentos.models import Documento, Revision

broken_count = 0
for d in Documento.objects.all():
    try:
        # Esto disparará el DoesNotExist si el ID apunta a la nada
        _ = d.ultima_revision
    except Revision.DoesNotExist:
        print(f"Buscando solución para: {d.codigo} (ID: {d.id})")
        # Intentar arreglarlo buscando la revisión más reciente real
        latest = d.revisiones.order_by('-creado_en').first()
        if latest:
            d.ultima_revision = latest
            d.save(update_fields=['ultima_revision'])
            print(f"  ✅ Re-vinculado a revisión: {latest.revision}")
        else:
            d.ultima_revision = None
            d.save(update_fields=['ultima_revision'])
            print("  ⚠️ No tiene revisiones, limpiando puntero.")
        broken_count += 1

print(f"\nFinalizado. Se arreglaron {broken_count} punteros rotos.")
