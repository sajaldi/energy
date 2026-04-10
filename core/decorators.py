from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from .models import ElementoApp

def mobile_permission_required(clave):
    """
    Decorador para restringir el acceso a vistas móviles según la configuración
    dinámica de ElementoApp.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Obtener secciones permitidas para el usuario
            secciones = ElementoApp.get_secciones_usuario(request.user)
            
            if clave in secciones:
                return view_func(request, *args, **kwargs)
            
            # Si no tiene permiso, redirigir al dashboard con alerta
            messages.error(request, f"No tienes permiso para acceder a esta sección ({clave}).")
            return redirect('core:mobile_dashboard')
            
        return _wrapped_view
    return decorator
