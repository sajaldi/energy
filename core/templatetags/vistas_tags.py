from django import template
from django.db.models import Q
from core.models import VistaPersonalizada

register = template.Library()

@register.inclusion_tag('admin/includes/saved_views_dropdown.html', takes_context=True)
def render_saved_views(context, cl=None):
    """
    Renderiza el dropdown de vistas guardadas en el change_list.
    """
    try:
        request = context.get('request')
        # Intentar obtener cl del contexto si no se pasó
        if cl is None:
            cl = context.get('cl') or context.get('changelist')
            
        if not request or not cl:
            return {'show': False}
            
        opts = getattr(cl, 'opts', None)
        if not opts:
            return {'show': False}
            
        app_label = opts.app_label
        model_name = opts.model_name
        
        vistas = []
        if request.user.is_authenticated:
            vistas = VistaPersonalizada.objects.filter(
                app_label=app_label,
                model_name=model_name
            ).filter(
                Q(usuario=request.user) | Q(es_publica=True)
            ).distinct()
            
        return {
            'vistas': vistas,
            'request': request,
            'cl': cl,
            'app_label': app_label,
            'model_name': model_name,
            'current_query': request.GET.urlencode(),
            'show': True
        }
    except Exception as e:
        # Fallback silencioso para evitar 500
        return {'show': False}
