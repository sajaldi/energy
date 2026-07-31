import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activos', '0074_rack_bodega_area'),
        ('presupuestos', '0072_add_grupo_requisicion'),
    ]

    operations = [
        # Drop the old varchar column directly via SQL
        migrations.RunSQL(
            sql="ALTER TABLE activos_categoria DROP COLUMN IF EXISTS codigo_exoneracion;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Add as ForeignKey (Django creates codigo_exoneracion_id)
        migrations.AddField(
            model_name='categoria',
            name='codigo_exoneracion',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='categorias_activos',
                to='presupuestos.codigoexoneracion',
                verbose_name='Código de exoneración',
                help_text='Código arancelario de exoneración fiscal vinculado a esta categoría',
            ),
        ),
    ]
