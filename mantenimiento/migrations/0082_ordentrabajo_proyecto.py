from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0010_alter_documentoproyecto_carpeta_and_more'),
        ('mantenimiento', '0081_tipo_kpis'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordentrabajo',
            name='proyecto',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ordenes_trabajo', to='proyectos.proyecto', verbose_name='Proyecto'),
        ),
    ]
