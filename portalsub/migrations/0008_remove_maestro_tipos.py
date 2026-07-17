from django.db import migrations

NOMBRES_MAESTROS = [
    'RTN',
    'Acta Constitutiva',
    'Contrato',
    'Constancia de Solvencia',
    'Certificación de Registro de Proveedores',
]

def delete_maestros(apps, schema_editor):
    TipoEntregable = apps.get_model('portalsub', 'TipoEntregable')
    EntregableContratista = apps.get_model('portalsub', 'EntregableContratista')
    DocumentoEntregable = apps.get_model('portalsub', 'DocumentoEntregable')

    tipos = list(TipoEntregable.objects.filter(nombre__in=NOMBRES_MAESTROS))
    tipo_ids = [t.id for t in tipos]

    DocumentoEntregable.objects.filter(tipo_entregable_id__in=tipo_ids).delete()
    EntregableContratista.objects.filter(tipo_entregable_id__in=tipo_ids).delete()
    TipoEntregable.objects.filter(id__in=tipo_ids).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('portalsub', '0007_remove_es_maestro'),
    ]

    operations = [
        migrations.RunPython(delete_maestros, reverse_code=migrations.RunPython.noop),
    ]
