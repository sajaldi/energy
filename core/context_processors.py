from .models import ConfiguracionUI

def ui_config(request):
    """
    Context processor to inject UI configuration into all templates.
    """
    try:
        config = ConfiguracionUI.objects.first()
    except:
        config = None
        
    if not config:
        # Default fallback values if no config exists in DB
        return {
            'ui_config': {
                'color_primario': '#007bff',
                'color_secundario': '#6c757d',
                'matriz_header_bg': '#f8f9fa',
                'matriz_border_color': '#dee2e6',
            }
        }

    return {'ui_config': config}
