from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, Count
from .models import SolicitudPago
from datetime import datetime
from django.http import HttpResponse, JsonResponse
from django.core.files.storage import default_storage
from django.core.cache import cache
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
import json
import os

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
    
    # Agrupar items por proveedor y calcular totales
    items_por_proveedor = {}
    for item in solicitud.items.all():
        prov_nombre = item.requisicion.proveedor.nombre if item.requisicion.proveedor else "Sin Proveedor Asignado"
        if prov_nombre not in items_por_proveedor:
            items_por_proveedor[prov_nombre] = {'lista_items': [], 'total': 0}
        items_por_proveedor[prov_nombre]['lista_items'].append(item)
        items_por_proveedor[prov_nombre]['total'] += (item.monto_solicitado or 0)

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

@login_required
def api_requisicion_detalle(request, pk):
    """
    Retorna detalles de una requisición y su historial de pagos en JSON.
    """
    from .models import Requisicion
    requisicion = get_object_or_404(Requisicion.objects.prefetch_related(
        'articulos', 
        'items_pago', 
        'items_pago__solicitud'
    ), pk=pk)
    
    articulos = []
    for art in requisicion.articulos.all():
        articulos.append({
            'descripcion': art.cr8ca_articulo,
            'cantidad': float(art.cr8ca_cantidad),
            'costo': float(art.cr8ca_costoaproximado or 0),
            'subtotal': float(art.subtotal)
        })
        
    pagos = []
    for item in requisicion.items_pago.all().order_by('-creado_en'):
        pagos.append({
            'solicitud_id': item.solicitud.pk,
            'descripcion': item.descripcion,
            'monto': float(item.monto_solicitado),
            'estatus': item.estatus,
            'fecha': item.creado_en.strftime("%d/%m/%Y")
        })
        
    data = {
        'id': requisicion.pk,
        'codigo': requisicion.cr8ca_requisicion,
        'asunto': requisicion.cr8ca_asunto,
        'proveedor': requisicion.proveedor.nombre if requisicion.proveedor else "No asignado",
        'total_estimado': float(requisicion.total_estimado),
        'total_pagado': float(requisicion.monto_pagado),
        'comentarios': requisicion.cr8ca_comentarios or "",
        'articulos': articulos,
        'pagos': pagos
    }
    
    return JsonResponse(data)

@login_required
@csrf_exempt
def api_update_requisicion_comentarios(request, pk):
    """
    Actualiza los comentarios de una requisición vía AJAX.
    """
    if request.method == 'POST':
        try:
            from .models import Requisicion
            data = json.loads(request.body)
            requisicion = get_object_or_404(Requisicion, pk=pk)
            requisicion.cr8ca_comentarios = data.get('comentarios', '')
            requisicion.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Solo POST'}, status=405)

@login_required
def exportar_solicitud_pago_excel(request, pk):
    """
    Genera un archivo Excel con el detalle de la solicitud de pago.
    """
    solicitud = get_object_or_404(SolicitudPago.objects.prefetch_related('items', 'items__requisicion'), pk=pk)
    
    wb = Workbook()
    ws = wb.active
    ws.title = f"Solicitud_{solicitud.pk}"
    
    # Estilos
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1e293b", end_color="1e293b", fill_type="solid")
    center_align = Alignment(horizontal="center")
    
    # Encabezado de la solicitud
    ws.merge_cells('A1:G1')
    ws['A1'] = f"SOLICITUD DE PAGO #{solicitud.pk}"
    ws['A1'].font = Font(size=14, bold=True)
    ws['A1'].alignment = center_align
    
    ws.append([])
    ws.append(["Fecha:", solicitud.fecha_solicitud.strftime("%d/%m/%Y")])
    ws.append(["Solicitante:", solicitud.usuario_solicitante.get_full_name() if solicitud.usuario_solicitante else "N/A"])
    ws.append(["Descripción:", solicitud.descripcion or ""])
    ws.append(["Estado:", solicitud.get_estado_display()])
    ws.append([])
    
    # Tabla de items
    headers = ["N° REQUISICIÓN", "PROVEEDOR", "ASUNTO", "DESCRIPCIÓN PAGO", "MONTO SOLICITADO", "PAGADO RQ", "AVANCE %"]
    ws.append(headers)
    
    # Aplicar estilos a headers
    for cell in ws[ws.max_row]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    for item in solicitud.items.all():
        total_rq = item.requisicion.cr8ca_totalenarticulos or 0
        pagado_rq = item.requisicion.monto_pagado or 0
        porcentaje = 0
        if total_rq > 0:
            porcentaje = ((pagado_rq + (item.monto_solicitado or 0)) / total_rq) * 100
        
        row = [
            item.requisicion.cr8ca_requisicion,
            item.requisicion.proveedor.nombre if item.requisicion.proveedor else "N/A",
            item.requisicion.cr8ca_asunto,
            item.descripcion,
            float(item.monto_solicitado or 0),
            float(pagado_rq),
            f"{porcentaje:.2f}%"
        ]
        ws.append(row)
        
    # Totales al final
    ws.append([])
    ws.append(["", "", "", "TOTAL SOLICITADO:", float(solicitud.total_solicitado or 0)])
    
    # Ajustar anchos
    for col in ws.columns:
        max_length = 0
        column_index = col[0].column
        column_letter = get_column_letter(column_index)
        for cell in col:
            try:
                if cell.value and len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        ws.column_dimensions[column_letter].width = min(max_length + 2, 50)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=Solicitud_Pago_{solicitud.pk}.xlsx'
    wb.save(response)
    return response

@login_required
def import_items_pago_background(request, pk):
    """
    Vista para subir archivo e iniciar la importación asíncrona de items.
    """
    solicitud = get_object_or_404(SolicitudPago, pk=pk)
    
    if request.method == 'POST' and request.FILES.get('archivo'):
        archivo = request.FILES['archivo']
        ext = os.path.splitext(archivo.name)[1].lower().replace('.', '')
        
        if ext not in ['csv', 'xls', 'xlsx']:
            return render(request, 'presupuestos/solicitudes_pago/import_items.html', {
                'solicitud': solicitud,
                'error': 'Formato no soportado. Use CSV, XLS o XLSX.'
            })
            
        # Guardar temporalmente
        path = default_storage.save(f'tmp/import_items_{request.user.id}_{datetime.now().timestamp()}.{ext}', archivo)
        
        # Iniciar tarea Celery
        from .tasks import import_items_solicitud_task
        import_items_solicitud_task.delay(
            path, ext, 
            user_id=request.user.id, 
            solicitud_id=solicitud.pk,
            verification_mode=True # Iniciar con verificación
        )
        
        return render(request, 'presupuestos/solicitudes_pago/import_items.html', {
            'solicitud': solicitud,
            'importing': True,
            'cache_key': f"import_items_pago_progress_{request.user.id}"
        })
        
    return render(request, 'presupuestos/solicitudes_pago/import_items.html', {'solicitud': solicitud})

@login_required
def import_items_pago_process(request):
    """
    API para confirmar la ejecución real (Import o Dry Run) tras la verificación.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            solicitud_id = data.get('solicitud_id')
            file_path = data.get('file_path')
            dry_run = data.get('dry_run', False)
            
            ext = os.path.splitext(file_path)[1].lower().replace('.', '')
            
            from .tasks import import_items_solicitud_task
            import_items_solicitud_task.delay(
                file_path, ext, 
                user_id=request.user.id, 
                solicitud_id=solicitud_id,
                verification_mode=False,
                dry_run=dry_run
            )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Solo POST'}, status=405)

@login_required
def import_items_pago_progress(request):
    """
    API para consultar el progreso de la importación desde el caché.
    """
    cache_key = f"import_items_pago_progress_{request.user.id}"
    data = cache.get(cache_key)
    return JsonResponse(data or {'status': 'waiting'})
