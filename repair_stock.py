import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from inventarios.models import Material, MovimientoInventario
from django.utils import timezone

material_id = 6066
material = Material.objects.filter(id=material_id).first()

if material:
    print(f"Buscando movimientos pendientes para {material.nombre} (ID: {material_id})...")
    pendientes = material.movimientos.filter(estado='PENDIENTE')
    count = pendientes.count()
    if count > 0:
        for m in pendientes:
            m.estado = 'APROBADO'
            m.fecha_aprobacion = timezone.now()
            m.aprobado_por = m.usuario if m.usuario else None
            m.save()
        print(f"Se aprobaron {count} movimientos.")
        material.recalcular_stock()
        print(f"Stock recalculado. Total: {material.get_stock_total()}")
    else:
        print("No se encontraron movimientos pendientes.")
        material.recalcular_stock()
        print(f"Recalculando stock de todos modos. Total: {material.get_stock_total()}")
else:
    print(f"Material {material_id} no encontrado.")
