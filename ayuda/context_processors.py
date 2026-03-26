from .models import ArticuloAyuda
import re

def help_context(request):
    """
    Context processor para detectar si hay ayuda contextual para la página actual del admin.
    """
    context_help = None
    path = request.path
    
    # DEBUG: print(f"[AYUDA] Path actual: {path}")
    
    # Detectar si estamos en el admin: /admin/app_label/model_name/...
    # Regex más flexible: busca el segundo y tercer componente después de /admin/
    parts = path.strip('/').split('/')
    if len(parts) >= 3 and parts[0] == 'admin':
        app_label = parts[1]
        model_name = parts[2]
        
        # DEBUG: print(f"[AYUDA] Buscando para {app_label}.{model_name}")
        
        # Buscar artículo marcado como contextual para esta app/modelo
        context_help = ArticuloAyuda.objects.filter(
            app_label=app_label,
            model_name=model_name,
            es_contextual=True
        ).first()
        
    return {
        'context_help_article': context_help
    }
