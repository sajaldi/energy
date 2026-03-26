from django.http import JsonResponse
from .models import ArticuloAyuda
from django.urls import reverse
import re

def check_context_help(request):
    path = request.GET.get('url', '')
    if not path:
        return JsonResponse({'help': None})
    
    parts = path.strip('/').split('/')
    if len(parts) >= 3 and parts[0] == 'admin':
        app_label = parts[1]
        model_name = parts[2]
        
        context_help = ArticuloAyuda.objects.filter(
            app_label=app_label,
            model_name=model_name,
            es_contextual=True
        ).first()
        
        if context_help:
            return JsonResponse({
                'help': {
                    'title': context_help.titulo,
                    'url': reverse('ayuda:detail', kwargs={'slug': context_help.slug}),
                }
            })
            
    return JsonResponse({'help': None})
