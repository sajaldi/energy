from django.contrib.auth.models import User, Group


def crear_notificacion(user, titulo, mensaje, tipo='INFO', modulo='SISTEMA', enlace='', emisor=None, icono=''):
    from .models import Notificacion

    if isinstance(user, User) and user.is_authenticated:
        icono_map = {
            'INFO': 'information-circle',
            'SUCCESS': 'checkmark-circle',
            'WARNING': 'warning',
            'ERROR': 'alert-circle',
        }
        if not icono:
            icono = icono_map.get(tipo, 'information-circle')

        return Notificacion.objects.create(
            user=user,
            emisor=emisor,
            titulo=titulo,
            mensaje=mensaje,
            tipo=tipo,
            modulo=modulo,
            enlace=enlace,
            icono=icono,
        )
    return None


def notificar_a_grupo(grupo_nombre, titulo, mensaje, tipo='INFO', modulo='SISTEMA', enlace='', emisor=None, icono=''):
    from .models import Notificacion

    try:
        grupo = Group.objects.get(name=grupo_nombre)
        notis = []
        icono_map = {
            'INFO': 'information-circle',
            'SUCCESS': 'checkmark-circle',
            'WARNING': 'warning',
            'ERROR': 'alert-circle',
        }
        if not icono:
            icono = icono_map.get(tipo, 'information-circle')

        for user in grupo.user_set.all():
            notis.append(Notificacion(
                user=user,
                emisor=emisor,
                titulo=titulo,
                mensaje=mensaje,
                tipo=tipo,
                modulo=modulo,
                enlace=enlace,
                icono=icono,
            ))
        if notis:
            Notificacion.objects.bulk_create(notis)
        return notis
    except Group.DoesNotExist:
        return []
