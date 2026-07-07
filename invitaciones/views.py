from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages

from .services import TokenService
from .exceptions import TokenNotFound, TokenExpired, TokenAlreadyUsed


def complete_registration(request):
    """
    Vista de completar registro desde el enlace de invitación.
    GET  : muestra el formulario de contraseña.
    POST : valida el token, setea la contraseña y activa el usuario.
    """
    raw_token = request.GET.get('token') or request.POST.get('token', '')

    if not raw_token:
        return render(request, 'invitaciones/invalid_token.html',
                      {'error': 'No se proporcionó un token de invitación.'})

    token_service = TokenService()

    # Validar el token
    try:
        token_obj = token_service.validate_token(raw_token)
    except TokenNotFound:
        return render(request, 'invitaciones/invalid_token.html',
                      {'error': 'El enlace de invitación no es válido.'})
    except TokenExpired:
        return render(request, 'invitaciones/invalid_token.html',
                      {'error': 'El enlace de invitación ha expirado. Solicita un nuevo envío.'})
    except TokenAlreadyUsed:
        return render(request, 'invitaciones/invalid_token.html',
                      {'error': 'Este enlace ya fue utilizado. Inicia sesión directamente.'})

    user = token_obj.user

    if request.method == 'POST':
        password1 = request.POST.get('password1', '').strip()
        password2 = request.POST.get('password2', '').strip()

        if not password1:
            return render(request, 'invitaciones/complete_registration.html',
                          {'token': raw_token, 'user': user, 'error': 'La contraseña no puede estar vacía.'})

        if password1 != password2:
            return render(request, 'invitaciones/complete_registration.html',
                          {'token': raw_token, 'user': user, 'error': 'Las contraseñas no coinciden.'})

        if len(password1) < 8:
            return render(request, 'invitaciones/complete_registration.html',
                          {'token': raw_token, 'user': user, 'error': 'La contraseña debe tener al menos 8 caracteres.'})

        # Activar usuario y setear contraseña
        user.set_password(password1)
        user.is_active = True
        user.save()

        # Actualizar estado del perfil
        perfil = getattr(user, 'perfil', None)
        if perfil:
            perfil.invitation_status = 'active'
            perfil.save(update_fields=['invitation_status'])

        # Consumir el token
        token_service.consume_token(token_obj)

        # Iniciar sesión automáticamente
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        messages.success(request, f'¡Bienvenido, {user.get_full_name() or user.username}! Tu cuenta ha sido activada.')
        return redirect('/')

    return render(request, 'invitaciones/complete_registration.html',
                  {'token': raw_token, 'user': user})
