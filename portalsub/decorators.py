from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def contratista_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('portalsub:login')
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        if not hasattr(request.user, 'perfil_contratista'):
            messages.error(request, 'No tienes acceso al portal de subcontratistas.')
            return redirect('portalsub:login')
        if not request.user.perfil_contratista.activo:
            messages.error(request, 'Tu cuenta está desactivada. Contacta al administrador.')
            return redirect('portalsub:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def get_empresa(request):
    if request.user.is_superuser:
        from mantenimiento.models import Empresa
        first = Empresa.objects.filter(activo=True).first()
        if first:
            return first
        return Empresa.objects.first()
    return request.user.perfil_contratista.empresa
