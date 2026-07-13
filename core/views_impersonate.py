from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse


@user_passes_test(lambda u: u.is_superuser)
def impersonate_start(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)

    if target_user == request.user:
        messages.warning(request, 'No puedes impersonarte a ti mismo.')
        return redirect(request.META.get('HTTP_REFERER', '/admin/'))

    request.session['impersonate_as_id'] = target_user.id
    request.session['impersonator_id'] = request.user.id

    messages.success(
        request,
        f'Ahora estás actuando como {target_user.get_full_name() or target_user.username}. '
        f'Detén la impersonación para volver a tu cuenta.'
    )
    return redirect('/app/')


def impersonate_stop(request):
    impersonator_id = request.session.get('impersonator_id')

    if not impersonator_id:
        messages.error(request, 'No estabas impersonando a ningún usuario.')
        return redirect('/admin/')

    request.session.pop('impersonate_as_id', None)
    request.session.pop('impersonator_id', None)

    from django.contrib.auth import login as auth_login
    from django.contrib.auth.models import User
    try:
        superuser = User.objects.get(pk=impersonator_id, is_superuser=True)
        auth_login(request, superuser, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Has vuelto a tu cuenta de superusuario ({superuser.get_full_name() or superuser.username}).')
    except User.DoesNotExist:
        messages.error(request, 'Error: el superusuario original ya no existe.')

    return redirect('/admin/')
