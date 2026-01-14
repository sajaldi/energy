from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages


def almacenes_required(view_func):
    """
    Decorador que verifica que el usuario pertenezca al grupo 'Almacenes'.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # Superusuarios siempre tienen acceso
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Verificar si el usuario pertenece al grupo 'Almacenes'
        if request.user.groups.filter(name='Almacenes').exists():
            return view_func(request, *args, **kwargs)
        
        # Si no tiene permisos, mostrar error
        messages.error(request, 'No tienes permisos para acceder al módulo de Almacén.')
        raise PermissionDenied("Acceso denegado. Se requiere pertenecer al grupo 'Almacenes'.")
    
    return _wrapped_view
