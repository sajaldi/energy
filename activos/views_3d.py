import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from .models.activo import Activo, Modelo
from .models.ubicacion import Ubicacion

import os
import uuid
from django.conf import settings
from django.core.files.storage import default_storage

@csrf_exempt
def subir_foto_3d(request):
    """
    Sube una imagen física al servidor para asociarla a un pin 3D.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    if not request.FILES.get('image'):
        return JsonResponse({'error': 'No se proporcionó ninguna imagen'}, status=400)
    
    try:
        image = request.FILES['image']
        # Generar nombre único para evitar colisiones
        ext = os.path.splitext(image.name)[1]
        filename = f"hotspot_{uuid.uuid4().hex}{ext}"
        
        path = os.path.join('hotspots', filename)
        saved_path = default_storage.save(path, image)
        
        # Devolver la URL correcta usando el motor de storage
        url = default_storage.url(saved_path)
        
        return JsonResponse({
            'status': 'success',
            'url': url
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def guardar_punto_3d(request):
    """
    Guarda o actualiza un hotspot/punto en el modelo 3D.
    Recibe: model_type, object_id, hotspots (lista JSON)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        model_type = data.get('model_type') # 'activo', 'modelo', 'ubicacion'
        object_id = data.get('object_id')
        hotspots = data.get('hotspots', [])

        if model_type == 'activo':
            obj = get_object_or_404(Activo, id=object_id)
        elif model_type == 'modelo':
            obj = get_object_or_404(Modelo, id=object_id)
        elif model_type == 'ubicacion':
            obj = get_object_or_404(Ubicacion, id=object_id)
        else:
            return JsonResponse({'error': 'Tipo de modelo no válido'}, status=400)

        # Guardamos la lista de hotspots directamente en el JSONField
        obj.puntos_3d_data = hotspots
        obj.save(update_fields=['puntos_3d_data'])

        return JsonResponse({'status': 'success', 'message': 'Puntos guardados correctamente'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
