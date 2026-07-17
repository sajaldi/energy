from django.db import migrations

TIPOS = [
    {'nombre': 'RTN', 'es_maestro': True},
    {'nombre': 'Acta Constitutiva', 'es_maestro': True},
    {'nombre': 'Contrato', 'es_maestro': True},
    {'nombre': 'Constancia de Solvencia', 'es_maestro': True},
    {'nombre': 'Certificación de Registro de Proveedores', 'es_maestro': True},
    {'nombre': 'Planilla IHSS', 'es_maestro': False},
    {'nombre': 'Planilla AFP', 'es_maestro': False},
    {'nombre': 'Altas y Bajas del Mes', 'es_maestro': False},
    {'nombre': 'Expediente Mensual', 'es_maestro': False},
    {'nombre': 'Reportes de Actividades', 'es_maestro': False},
    {'nombre': 'Bitácora de Trabajo', 'es_maestro': False},
    {'nombre': 'Fotografías de Avance', 'es_maestro': False},
]

def seed_tipos(apps, schema_editor):
    TipoEntregable = apps.get_model('portalsub', 'TipoEntregable')
    for t in TIPOS:
        TipoEntregable.objects.get_or_create(
            nombre=t['nombre'],
            defaults={'es_maestro': t['es_maestro']}
        )

def seed_por_empresa(apps, schema_editor):
    TipoEntregable = apps.get_model('portalsub', 'TipoEntregable')
    EntregableContratista = apps.get_model('portalsub', 'EntregableContratista')
    Empresa = apps.get_model('mantenimiento', 'Empresa')
    PerfilContratista = apps.get_model('portalsub', 'PerfilContratista')

    empresa_ids = list(PerfilContratista.objects.filter(
        activo=True, empresa__activo=True
    ).values_list('empresa_id', flat=True).distinct())

    if not empresa_ids:
        return

    tipos = list(TipoEntregable.objects.all())
    existentes = set(
        EntregableContratista.objects.filter(empresa_id__in=empresa_ids)
        .values_list('empresa_id', 'tipo_entregable_id')
    )

    to_create = [
        EntregableContratista(empresa_id=eid, tipo_entregable=tipo, obligatorio=tipo.es_maestro)
        for eid in empresa_ids
        for tipo in tipos
        if (eid, tipo.id) not in existentes
    ]

    if to_create:
        EntregableContratista.objects.bulk_create(to_create, ignore_conflicts=True)

class Migration(migrations.Migration):

    dependencies = [
        ('portalsub', '0005_tipoentregable_historialpersonal_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_tipos, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(seed_por_empresa, reverse_code=migrations.RunPython.noop),
    ]
