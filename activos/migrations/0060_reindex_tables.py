from django.db import migrations

class Migration(migrations.Migration):
    """
    Mantenimiento: REINDEX de tablas críticas para corregir error de Postgres
    'posting list tuple with 5 items cannot be split at offset 18'.
    Esto reconstruye los índices corruptos.
    """
    dependencies = [
        ('activos', '0059_fix_puntos_3d_data_nullable'),
        ('callcenter', '0001_initial'), # Aseguramos que la tabla de tickets existe
    ]

    operations = [
        # Reconstruir índices de las tablas que están dando problemas durante el sync
        migrations.RunSQL("REINDEX TABLE activos_ubicacion;", reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL("REINDEX TABLE callcenter_solicitudticket;", reverse_sql=migrations.RunSQL.noop),
    ]
