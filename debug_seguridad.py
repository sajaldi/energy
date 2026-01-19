import os
import django
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'energia.settings')
django.setup()

from django.contrib.auth.models import User
from seguridad.models import (
    TipoIncidente, Incidente,
    TipoInspeccion, Inspeccion,
    AsignacionEPP,
    AnalisisRiesgo,
    TipoPermiso, PermisoTrabajo
)
from inventarios.models import Material, CategoriaMaterial

def run_checks():
    print("--- Verificando App Seguridad ---")
    
    # 1. Verificar Usuario
    user = User.objects.first()
    if not user:
        print("No hay usuarios. Creando uno de prueba.")
        user = User.objects.create_user('test_seguridad', 'test@example.com', 'pass')
    print(f"Usuario de prueba: {user.username}")

    # 2. Incidentes
    tipo_inc, _ = TipoIncidente.objects.get_or_create(nombre="Accidente Vehicular")
    inc = Incidente.objects.create(
        titulo="Colisión Menor",
        tipo=tipo_inc,
        descripcion="Golpe en parachoques",
        reportado_por=user,
        ubicacion_texto="Estacionamiento"
    )
    print(f"Creado Incidente: {inc}")

    # 3. Inspecciones
    tipo_insp, _ = TipoInspeccion.objects.get_or_create(nombre="Extintores")
    insp = Inspeccion.objects.create(
        tipo=tipo_insp,
        inspector=user,
        resultado_global='APROBADO'
    )
    print(f"Creada Inspección: {insp}")

    # 4. EPP
    cat_epp, _ = CategoriaMaterial.objects.get_or_create(nombre="EPP")
    material_epp, _ = Material.objects.get_or_create(
        sku="EPP-CASCO-001",
        defaults={'nombre': 'Casco de Seguridad', 'categoria': cat_epp}
    )
    asignacion = AsignacionEPP.objects.create(
        miembro=user,
        material=material_epp,
        cantidad=1
    )
    print(f"Asignado EPP: {asignacion}")

    # 5. AST
    ast = AnalisisRiesgo.objects.create(
        descripcion_trabajo="Reparación en Altura",
        lider=user
    )
    print(f"Creado AST: {ast}")

    # 6. Permisos
    tipo_permiso, _ = TipoPermiso.objects.get_or_create(nombre="Trabajo en Altura")
    permiso = PermisoTrabajo.objects.create(
        tipo=tipo_permiso,
        descripcion_trabajo="Cambio de luminarias",
        fecha_inicio=timezone.now(),
        fecha_fin=timezone.now() + timezone.timedelta(hours=4),
        solicitante=user
    )
    print(f"Creado Permiso: {permiso}")

    print("\n--- Verificación Exitosa ---")

if __name__ == '__main__':
    try:
        run_checks()
    except Exception as e:
        print(f"ERROR: {e}")
