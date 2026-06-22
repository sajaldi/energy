from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('presupuestos', '0045_aumentar_longitud_cr8ca_articulo'),
    ]

    operations = [
        migrations.AddField(
            model_name='requisicion',
            name='isv',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=0,
                max_digits=15,
                null=True,
                verbose_name='ISV (Impuesto Sobre Ventas)',
            ),
        ),
    ]
