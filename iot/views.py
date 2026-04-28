from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import OuterRef, Subquery
from asgiref.sync import sync_to_async
import asyncio
from .models import BACnetDevice, Telemetry, BACnetPoint, BACnetSchedule
from .services import bacnet_service

def dashboard(request):
    """Vista principal para monitoreo IoT"""
    devices = BACnetDevice.objects.all().prefetch_related('points')
    
    last_reading = Telemetry.objects.filter(point=OuterRef('pk')).order_by('-timestamp')
    points = BACnetPoint.objects.select_related('device').annotate(
        last_value=Subquery(last_reading.values('value')[:1]),
        last_time=Subquery(last_reading.values('timestamp')[:1])
    )
    
    schedules = BACnetSchedule.objects.all().select_related('device')
    
    context = {
        'devices': devices,
        'points': points,
        'schedules': schedules,
        'title': 'Monitoreo BMS (Reliable Controls)'
    }
    return render(request, 'iot/dashboard.html', context)

async def _do_device_sync(device_id):
    """Logica de sincronizacion usando el servicio global"""
    try:
        device = await sync_to_async(BACnetDevice.objects.get)(pk=device_id)
        points = await sync_to_async(lambda: list(BACnetPoint.objects.filter(device=device)))()
        
        results = []
        for p in points:
            try:
                addr = f"{device.address} {p.object_type} {p.instance} presentValue"
                # Usamos el servicio global persistente
                val = await bacnet_service.read_point(addr)
                
                await sync_to_async(Telemetry.objects.create)(point=p, value=float(val))
                results.append({'point_id': p.id, 'value': float(val)})
            except Exception as e:
                print(f"Error leyendo punto {p.name}: {e}")
                continue
        
        return {'success': True, 'results': results}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def sync_device(request, device_id):
    """Endpoint AJAX para sincronizar un dispositivo"""
    if request.method == 'POST':
        # Ejecutamos la sincronizacion async
        result = asyncio.run(_do_device_sync(device_id))
        return JsonResponse(result)
    return JsonResponse({'success': False, 'error': 'Metodo no permitido'}, status=405)
