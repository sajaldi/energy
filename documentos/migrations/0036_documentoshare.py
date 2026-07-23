from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('documentos', '0035_add_proveedor_to_groqapikey'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentoShare',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('usuario', 'Usuario Específico'), ('grupo', 'Grupo'), ('publico', 'Público (Todos)')], max_length=10, verbose_name='Tipo')),
                ('puede_ver', models.BooleanField(default=True, verbose_name='Puede Ver')),
                ('puede_editar', models.BooleanField(default=False, verbose_name='Puede Editar')),
                ('puede_eliminar', models.BooleanField(default=False, verbose_name='Puede Eliminar')),
                ('puede_compartir', models.BooleanField(default=False, verbose_name='Puede Re-compartir')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('expira_en', models.DateTimeField(blank=True, help_text='Dejar vacío para acceso permanente.', null=True, verbose_name='Expira en')),
                ('nota', models.CharField(blank=True, default='', help_text='Motivo o comentario sobre por qué se compartió.', max_length=255, verbose_name='Nota')),
                ('compartido_a_grupo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='documentos_compartidos_grupo', to='auth.group', verbose_name='Grupo')),
                ('compartido_a_usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='documentos_compartidos_conmigo', to=settings.AUTH_USER_MODEL, verbose_name='Usuario')),
                ('compartido_por', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documentos_compartidos_por', to=settings.AUTH_USER_MODEL, verbose_name='Compartido por')),
                ('documento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shares', to='documentos.documento', verbose_name='Documento')),
            ],
            options={
                'verbose_name': 'Compartición de Documento',
                'verbose_name_plural': 'Comparticiones de Documentos',
                'ordering': ['-creado_en'],
                'indexes': [
                    models.Index(fields=['documento', 'tipo'], name='documentos__documen_bc14b8_idx'),
                    models.Index(fields=['compartido_a_usuario'], name='documentos__compart_cfafbd_idx'),
                    models.Index(fields=['compartido_a_grupo'], name='documentos__compart_c955a9_idx'),
                ],
            },
        ),
    ]
