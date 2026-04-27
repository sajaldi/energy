from django.shortcuts import render
from .models import BACnetDevice, Telemetry, BACnetPoint
from django.db.models import OuterRef, Subquery

def dashboard(request):
    """
    Vista principal para monitoreo IoT.
    Muestra dispositivos, puntos y sus últimas lecturas.
    """
    devices = BACnetDevice.objects.all().prefetch_related('points')
    
    # Subquery para obtener la última lectura de cada punto de manera eficiente
    last_reading = Telemetry.objects.filter(point=OuterRef('pk')).order_by('-timestamp')
    points = BACnetPoint.objects.select_related('device').annotate(
        last_value=Subquery(last_reading.values('value')[:1]),
        last_time=Subquery(last_reading.values('timestamp')[:1])
    )
    
    context = {
        'devices': devices,
        'points': points,
        'title': 'Monitoreo BMS (Reliable Controls)'
    }
    return render(request, 'iot/dashboard.html', context)
