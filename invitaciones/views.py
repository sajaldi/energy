from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .services import TokenService
from .exceptions import TokenNotFound, TokenExpired, TokenAlreadyUsed


@login_required
def complete_registration(request):
    """
    Vista de completar registro desde el enlace de invitación.
    GET  : muestra el formulario.
    POST : valida token, setea contraseña, guarda perfil y activa usuario.
    """
    raw_token = request.GET.get('token') or request.POST.get('token', '')

    if not raw_token:
        return render(request, 'invitaciones/invalid_token.html',
                      {'error': 'No se proporcionó un token de invitación.'})

    token_service = TokenService()
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

    # Cargar departamentos para el select
    from core.models import Departamento
    departamentos = Departamento.objects.all().order_by('nombre')

    if request.method == 'POST':
        first_name  = request.POST.get('first_name', '').strip()
        last_name   = request.POST.get('last_name', '').strip()
        telefono    = request.POST.get('telefono', '').strip()
        departamento_id = request.POST.get('departamento', '').strip()
        password1   = request.POST.get('password1', '').strip()
        password2   = request.POST.get('password2', '').strip()

        ctx = {'token': raw_token, 'user': user, 'departamentos': departamentos,
               'v_first_name': first_name, 'v_last_name': last_name,
               'v_telefono': telefono, 'v_departamento': departamento_id}

        if not first_name:
            ctx['error'] = 'El nombre es requerido.'
            return render(request, 'invitaciones/complete_registration.html', ctx)
        if not last_name:
            ctx['error'] = 'El apellido es requerido.'
            return render(request, 'invitaciones/complete_registration.html', ctx)
        if not password1 or len(password1) < 8:
            ctx['error'] = 'La contraseña debe tener al menos 8 caracteres.'
            return render(request, 'invitaciones/complete_registration.html', ctx)
        if password1 != password2:
            ctx['error'] = 'Las contraseñas no coinciden.'
            return render(request, 'invitaciones/complete_registration.html', ctx)

        # Actualizar usuario
        user.first_name = first_name
        user.last_name  = last_name
        user.set_password(password1)
        user.is_active  = True
        user.save()

        # Actualizar perfil
        perfil = getattr(user, 'perfil', None)
        if perfil:
            if telefono:
                perfil.telefono = telefono
            if departamento_id:
                try:
                    perfil.departamento_id = int(departamento_id)
                except (ValueError, TypeError):
                    pass
            perfil.invitation_status = 'active'
            perfil.save()

        token_service.consume_token(token_obj)
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'¡Bienvenido, {user.get_full_name()}! Tu cuenta ha sido activada.')
        return redirect('/')

    return render(request, 'invitaciones/complete_registration.html', {
        'token': raw_token,
        'user': user,
        'departamentos': departamentos,
    })
