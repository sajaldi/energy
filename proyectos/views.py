from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from .models import Actividad, Proyecto
import json

@csrf_exempt
@staff_member_required
def crear_actividad_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nombre = data.get('nombre')
            proyecto_id = data.get('proyecto_id')
            prioridad = data.get('prioridad', 'MEDIA')
            
            if not nombre or not proyecto_id:
                return JsonResponse({'status': 'error', 'message': 'Faltan datos obligatorios'}, status=400)
            
            proyecto = Proyecto.objects.get(pk=proyecto_id)
            
            # Calcular orden (último + 1)
            ultimo_orden = Actividad.objects.filter(proyecto=proyecto).order_by('-orden').first()
            orden = (ultimo_orden.orden + 1) if ultimo_orden else 1
            
            actividad = Actividad.objects.create(
                proyecto=proyecto,
                nombre=nombre,
                prioridad=prioridad,
                estado='PENDIENTE',
                orden=orden,
                asignado_a=request.user # Asignar al creador por defecto o null? Mejor al creador
            )
            
            return JsonResponse({
                'status': 'success',
                'actividad': {
                    'id': actividad.id,
                    'nombre': actividad.nombre,
                    'color': actividad.color,
                    'estado': actividad.get_estado_display(),
                    'proyecto_codigo': proyecto.codigo
                }
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
