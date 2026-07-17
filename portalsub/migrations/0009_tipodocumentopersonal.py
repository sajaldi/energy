from django.db import migrations, models
import django.db.models.deletion


TIPOS_INICIALES = [
    {'nombre': 'CV Actualizado'},
    {'nombre': 'Certificaciones'},
    {'nombre': 'Copia del DNI'},
    {'nombre': 'Antecedentes Penales'},
    {'nombre': 'Otro'},
]


def crear_tipos(apps, schema_editor):
    TipoDocumentoPersonal = apps.get_model('portalsub', 'TipoDocumentoPersonal')
    for i, t in enumerate(TIPOS_INICIALES):
        TipoDocumentoPersonal.objects.get_or_create(
            nombre=t['nombre'],
            defaults={'orden': i},
        )


def migrar_tipos(apps, schema_editor):
    TipoDocumentoPersonal = apps.get_model('portalsub', 'TipoDocumentoPersonal')
    DocumentoPersonal = apps.get_model('portalsub', 'DocumentoPersonal')
    mapping = {
        'CV': 'CV Actualizado',
        'CERTIFICACION': 'Certificaciones',
        'DNI': 'Copia del DNI',
        'ANTECEDENTES': 'Antecedentes Penales',
        'OTRO': 'Otro',
    }
    for doc in DocumentoPersonal.objects.all():
        nombre = mapping.get(doc.tipo)
        if nombre:
            tipo_obj = TipoDocumentoPersonal.objects.get(nombre=nombre)
            doc.tipo_fk = tipo_obj
            doc.save()


class Migration(migrations.Migration):

    dependencies = [
        ('portalsub', '0008_remove_maestro_tipos'),
    ]

    operations = [
        migrations.CreateModel(
            name='TipoDocumentoPersonal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True, verbose_name='Nombre')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
                ('orden', models.IntegerField(default=0, verbose_name='Orden')),
            ],
            options={
                'verbose_name': 'Tipo de Documento Personal',
                'verbose_name_plural': 'Tipos de Documentos Personales',
                'ordering': ['orden', 'nombre'],
            },
        ),
        migrations.RunPython(crear_tipos, reverse_code=migrations.RunPython.noop),
        migrations.AddField(
            model_name='documentopersonal',
            name='tipo_fk',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='portalsub.tipodocumentopersonal', verbose_name='Tipo de documento'),
        ),
        migrations.RunPython(migrar_tipos, reverse_code=migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='documentopersonal',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='documentopersonal',
            name='tipo',
        ),
        migrations.RenameField(
            model_name='documentopersonal',
            old_name='tipo_fk',
            new_name='tipo',
        ),
        migrations.AlterUniqueTogether(
            name='documentopersonal',
            unique_together={('tecnico', 'tipo')},
        ),
        migrations.AlterField(
            model_name='documentopersonal',
            name='tipo',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='portalsub.tipodocumentopersonal', verbose_name='Tipo de documento'),
        ),
        migrations.AlterModelOptions(
            name='documentopersonal',
            options={'ordering': ['tipo__orden', 'tipo__nombre'], 'verbose_name': 'Documento del Personal', 'verbose_name_plural': 'Documentos del Personal'},
        ),
    ]
