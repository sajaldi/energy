from django.db import migrations


def migrate_from_mantenimiento(apps, schema_editor):
    NotificacionOld = apps.get_model('mantenimiento', 'NotificacionMantenimiento')
    NotificacionNew = apps.get_model('notificaciones', 'Notificacion')
    User = apps.get_model('auth', 'User')

    if not NotificacionOld.objects.exists():
        return

    icono_map = {
        'SUCCESS': 'checkmark-circle',
        'ERROR': 'alert-circle',
        'WARNING': 'warning',
        'INFO': 'information-circle',
    }

    new_notifs = []
    for old in NotificacionOld.objects.all().iterator():
        try:
            user = User.objects.get(pk=old.user_id)
        except User.DoesNotExist:
            continue
        new_notifs.append(NotificacionNew(
            user=user,
            titulo=old.get_tipo_display() if hasattr(old, 'get_tipo_display') else 'Notificación',
            mensaje=old.mensaje,
            tipo=old.tipo,
            modulo='SISTEMA',
            icono=icono_map.get(old.tipo, 'information-circle'),
            leida=old.leida,
            creado_en=old.creado_en,
        ))
    if new_notifs:
        NotificacionNew.objects.bulk_create(new_notifs)


class Migration(migrations.Migration):

    dependencies = [
        ('notificaciones', '0001_initial'),
        ('mantenimiento', '0086_tecnicopuesto_telefono_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_from_mantenimiento, migrations.RunPython.noop),
    ]
