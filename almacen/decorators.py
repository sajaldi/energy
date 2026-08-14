from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages


def almacenes_required(view_func):
    """
    Decorador que verifica que el usuario pertenezca al grupo 'Almacenes' o 'ALMACEN'.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # Verificar si el usuario pertenece al grupo 'Almacenes' o 'ALMACEN'
        if request.user.groups.filter(name__in=['Almacenes', 'ALMACEN']).exists():
            return view_func(request, *args, **kwargs)
        
        # Si no tiene permisos, mostrar error
        messages.error(request, 'No tienes permisos para acceder al módulo de Almacén.')
        raise PermissionDenied("Acceso denegado. Se requiere pertenecer al grupo 'Almacenes' o 'ALMACEN'.")
    
    return _wrapped_view


def almacenes_o_procura_tecnica_required(view_func):
    """
    Decorador que verifica que el usuario pertenezca a 'Almacenes'/'ALMACEN'
    o al grupo 'Procura_Tecnica' (procesa materiales NUEVOS y verifica duplicados).
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.groups.filter(name__in=['Almacenes', 'ALMACEN', 'Procura_Tecnica', 'PROCURA_TECNICA']).exists():
            return view_func(request, *args, **kwargs)

        messages.error(request, 'No tienes permisos para acceder al módulo de Almacén.')
        raise PermissionDenied("Acceso denegado. Se requiere pertenecer al grupo 'Almacenes' o 'Procura_Tecnica'.")

    return _wrapped_view
