from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import VisorPlano, PinPlano, Activo
import json
from django.views.decorators.csrf import csrf_exempt

def visor_plano(request, visor_id):
    visor = get_object_or_404(VisorPlano, pk=visor_id)
    # Prefetch activos for performance in the modal
    activos = Activo.objects.all().order_by('nombre')
    
    return render(request, 'activos/visor_plano.html', {
        'visor': visor,
        'activos': activos
    })

@csrf_exempt
def guardar_pin(request):
    if request.method == 'POST':
        try:
            # Soportar tanto JSON como FormData (para archivos)
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST

            pin_id = data.get('id')
            visor_id = data.get('visor_id')
            activo_id = data.get('activo_id')
            x = float(data.get('x'))
            y = float(data.get('y'))
            color = data.get('color', '#FF0000')
            nota = data.get('nota', '')

            if pin_id and pin_id != 'null':
                pin = get_object_or_404(PinPlano, id=pin_id)
            else:
                pin = PinPlano(visor_id=visor_id)

            if activo_id:
                pin.activo_id = activo_id
            else:
                pin.activo = None
                
            pin.x = x
            pin.y = y
            pin.color = color
            pin.nota = nota
            pin.save()

            # Guardar fotos si vienen en la petición
            if 'fotos' in request.FILES:
                from .models import PinFoto
                for f in request.FILES.getlist('fotos'):
                    PinFoto.objects.create(pin=pin, imagen=f)

            # Obtener URLs de las fotos
            fotos_urls = [f.imagen.url for f in pin.fotos.all()]

            return JsonResponse({
                'status': 'success',
                'pin_id': pin.id,
                'activo_id': pin.activo.id if pin.activo else None,
                'nombre_activo': pin.activo.nombre if pin.activo else 'Sin activo',
                'codigo_externo': pin.activo.codigo_interno if pin.activo else '',
                'nota': pin.nota,
                'fotos': fotos_urls
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@csrf_exempt
def eliminar_pin(request, pin_id):
    if request.method == 'POST':
        pin = get_object_or_404(PinPlano, id=pin_id)
        pin.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=405)
