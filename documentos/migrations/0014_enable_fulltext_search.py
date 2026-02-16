# Generated migration for full-text search on contenido_texto

from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documentos', '0013_n8nchathistory'),
    ]

    operations = [
        # Habilitar extensión pg_trgm para búsqueda de texto
        TrigramExtension(),
        
        # Agregar índices para búsqueda rápida
        migrations.AlterModelOptions(
            name='documento',
            options={'verbose_name': 'Documento', 'verbose_name_plural': 'Documentos'},
        ),
        migrations.AddIndex(
            model_name='documento',
            index=models.Index(fields=['codigo'], name='documentos_d_codigo_idx'),
        ),
        migrations.AddIndex(
            model_name='documento',
            index=models.Index(fields=['estado_actual'], name='documentos_d_estado_idx'),
        ),
        migrations.AddIndex(
            model_name='documento',
            index=models.Index(fields=['creado_en'], name='documentos_d_creado_idx'),
        ),
        # Índice GIN para búsqueda de texto completo
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS contenido_texto_gin_idx ON documentos_documento USING gin (contenido_texto gin_trgm_ops);",
            reverse_sql="DROP INDEX IF EXISTS contenido_texto_gin_idx;",
        ),
    ]
