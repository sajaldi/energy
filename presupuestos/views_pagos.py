from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, Count
from .models import SolicitudPago
from datetime import datetime

@login_required
def dashboard_pagos(request):
    """
    Dashboard moderno para visualizar Solicitudes de Pago.
    """
    # Filtros capturados de GET
    estado_filter = request.GET.get('estado')
    search_query = request.GET.get('q')

    # QuerySet Base optimized for items
    solicitudes = SolicitudPago.objects.prefetch_related('items', 'items__requisicion').all().order_by('-fecha_solicitud')

    # Aplicar filtros
    if estado_filter:
        solicitudes = solicitudes.filter(estado=estado_filter)
    
    if search_query:
        solicitudes = solicitudes.filter(
            Q(descripcion__icontains=search_query) | 
            Q(usuario_solicitante__username__icontains=search_query) |
            Q(pk__icontains=search_query)
        )

    # Métricas Globales (Cards Superiores)
    total_solicitudes = solicitudes.count()
    
    # Calculamos totales en Python para aprovechar las properties (ya que son campos calculados complejos)
    # Si fueran muchos registros, esto debería optimizarse con anotaciones DB, 
    # pero por ahora usaremos las properties ya definidas en el modelo para consistencia.
    monto_global_solicitado = sum(s.total_solicitado for s in solicitudes)
    monto_global_aprobado = sum(s.total_aprobado for s in solicitudes)
    monto_global_pagado = sum(s.total_pagado for s in solicitudes)

    # Conteo por estados para badges rápidos
    conteo_estados = {
        'ABIERTA': solicitudes.filter(estado='ABIERTA').count(),
        'EN_REVISION': solicitudes.filter(estado='EN_REVISION').count(),
        'CERRADA': solicitudes.filter(estado='CERRADA').count(),
    }

    context = {
        'solicitudes': solicitudes,
        'metrics': {
            'total_count': total_solicitudes,
            'total_solicitado': monto_global_solicitado,
            'total_aprobado': monto_global_aprobado,
            'total_pagado': monto_global_pagado,
            'total_pendiente': monto_global_aprobado - monto_global_pagado,
        },
        'conteo_estados': conteo_estados,
        'current_filter': estado_filter,
        'search_query': search_query,
        'today': datetime.now()
    }

    return render(request, 'presupuestos/solicitudes_pago/dashboard.html', context)

@login_required
def detalle_solicitud_pago(request, pk):
    """
    Vista detallada de una Solicitud de Pago.
    """
    solicitud = get_object_or_404(SolicitudPago.objects.prefetch_related('items', 'items__requisicion'), pk=pk)
    
    from .models import Requisicion
    requisiciones = Requisicion.objects.all().order_by('-cr8ca_requisicion')
    
    # Agrupar items por proveedor
    items_por_proveedor = {}
    for item in solicitud.items.all():
        prov_nombre = item.requisicion.proveedor.nombre if item.requisicion.proveedor else "Sin Proveedor Asignado"
        if prov_nombre not in items_por_proveedor:
            items_por_proveedor[prov_nombre] = []
        items_por_proveedor[prov_nombre].append(item)

    context = {
        'solicitud': solicitud,
        'requisiciones': requisiciones,
        'items_por_proveedor': items_por_proveedor,
    }
    
    return render(request, 'presupuestos/solicitudes_pago/detalle.html', context)

from django.http import JsonResponse
import json

@login_required
def api_update_item_pago(request):
    """
    Actualiza monto o descripción de un item de solicitud de pago.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('id')
            campo = data.get('campo')
            valor = data.get('valor')
            
            from .models import ItemSolicitudPago
            item = get_object_or_404(ItemSolicitudPago, pk=item_id)
            
            if campo == 'monto_solicitado':
                item.monto_solicitado = valor
            elif campo == 'descripcion':
                item.descripcion = valor
                
            item.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Solo POST'}, status=405)

@login_required
def api_add_requisicion_pago(request):
    """
    Agrega una requisición a una solicitud de pago existente.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            solicitud_id = data.get('solicitud_id')
            requisicion_id = data.get('requisicion_id')
            monto = data.get('monto', 0)
            descripcion = data.get('descripcion', '')
            
            from .models import ItemSolicitudPago, Requisicion, SolicitudPago
            solicitud = get_object_or_404(SolicitudPago, pk=solicitud_id)
            requisicion = get_object_or_404(Requisicion, pk=requisicion_id)
            
            # Validar duplicados en LA MISMA solicitud
            if ItemSolicitudPago.objects.filter(solicitud=solicitud, requisicion=requisicion).exists():
                return JsonResponse({
                    'status': 'error', 
                    'message': f'La requisición {requisicion.cr8ca_requisicion} ya existe en esta solicitud.'
                }, status=400)
            
            ItemSolicitudPago.objects.create(
                solicitud=solicitud,
                requisicion=requisicion,
                monto_solicitado=monto,
                descripcion=descripcion
            )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Solo POST'}, status=405)
