from .models import ConfiguracionUI

def ui_config(request):
    """
    Context processor to inject UI configuration into all templates.
    """
    context = {}
    
    try:
        config = ConfiguracionUI.objects.first()
    except:
        config = None
        
    if not config:
        context['ui_config'] = {
            'color_primario': '#007bff',
            'color_secundario': '#6c757d',
            'matriz_header_bg': '#f8f9fa',
            'matriz_border_color': '#dee2e6',
        }
    else:
        context['ui_config'] = config

    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            from notificaciones.models import Notificacion
            context['notificaciones_no_leidas'] = Notificacion.conteo_no_leidas(request.user)
        except Exception:
            context['notificaciones_no_leidas'] = 0
    else:
        context['notificaciones_no_leidas'] = 0

    return context
