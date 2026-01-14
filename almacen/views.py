from django.shortcuts import render, redirect, get_object_or_404
import json
from decimal import Decimal
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .decorators import almacenes_required
from inventarios.models import Material, MovimientoInventario, StockRecord, CategoriaMaterial, SolicitudMaterial
from activos.models.ubicacion import Ubicacion
from activos.models.activo import Marca
from django.db import transaction


@almacenes_required
def dashboard(request):
    """
    Dashboard principal del módulo de almacén.
    Muestra estadísticas y accesos rápidos.
    """
    # Estadísticas de solicitudes
    solicitudes_pendientes = SolicitudMaterial.objects.filter(estado='PENDIENTE').count()
    solicitudes_hoy = SolicitudMaterial.objects.filter(
        fecha_solicitud__date=timezone.now().date(),
        estado='PENDIENTE'
    ).count()
    
    # Materiales con stock bajo
    materiales_stock_bajo = []
    for material in Material.objects.all():
        stock_total = material.get_stock_total()
        if stock_total < material.stock_minimo:
            materiales_stock_bajo.append({
                'material': material,
                'stock_actual': stock_total,
                'stock_minimo': material.stock_minimo,
                'diferencia': material.stock_minimo - stock_total
            })
    
    # Últimas solicitudes (Órdenes)
    ultimas_ordenes = SolicitudMaterial.objects.filter(
        estado='PENDIENTE'
    ).select_related('usuario', 'ubicacion_origen').prefetch_related('items').order_by('-fecha_solicitud')[:10]
    
    # Estadísticas por estado
    stats_por_estado = SolicitudMaterial.objects.values('estado').annotate(total=Count('id'))
    
    context = {
        'solicitudes_pendientes': solicitudes_pendientes,
        'solicitudes_hoy': solicitudes_hoy,
        'materiales_stock_bajo': materiales_stock_bajo[:10],
        'ultimas_solicitudes': ultimas_ordenes,
        'stats_por_estado': stats_por_estado,
        'total_materiales': Material.objects.count(),
    }
    
    return render(request, 'almacen/dashboard.html', context)


@almacenes_required
def solicitudes_pendientes(request):
    """Lista de órdenes de salida pendientes."""
    # Filtros
    usuario_filtro = request.GET.get('usuario', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    
    # Query base
    ordenes = SolicitudMaterial.objects.filter(estado='PENDIENTE').select_related(
        'usuario', 'ubicacion_origen', 'orden_trabajo'
    ).prefetch_related('items', 'items__material').order_by('-fecha_solicitud')
    
    # Aplicar filtros
    if usuario_filtro:
        ordenes = ordenes.filter(usuario__username__icontains=usuario_filtro)
    
    if fecha_desde:
        ordenes = ordenes.filter(fecha_solicitud__date__gte=fecha_desde)
    
    context = {
        'ordenes': ordenes,
        'usuario_filtro': usuario_filtro,
        'fecha_desde': fecha_desde,
    }
    
    return render(request, 'almacen/solicitudes_pendientes.html', context)


@almacenes_required
def detalle_orden(request, orden_id):
    """Detalle de una orden para que el almacenista procese el despacho."""
    orden = get_object_or_404(SolicitudMaterial.objects.prefetch_related('items', 'items__material'), id=orden_id)
    
    # Preparar items con stock disponible en origen (agregado por ubicación específica)
    items_info = []
    for item in orden.items.all():
        # Obtener stock de CUALQUIER almacén (no solo del solicitado)
        stock_records = StockRecord.objects.filter(
            material=item.material, 
            cantidad__gt=0
        ).select_related('ubicacion').order_by('ubicacion__nombre', 'ubicacion_especifica')
        
        # Lista de celdas/ubicaciones con stock para el selector (Global)
        ubicaciones_disponibles = [
            {
                'ubicacion_id': sr.ubicacion.id,
                'almacen': sr.ubicacion.nombre,
                'especifica': sr.ubicacion_especifica or '', # Mantener original para el valor
                'especifica_display': sr.ubicacion_especifica or 'General', # Solo para el texto
                'cantidad': float(sr.cantidad)
            } for sr in stock_records
        ]
        
        total_acumulado = sum(float(sr.cantidad) for sr in stock_records)
        
        items_info.append({
            'item': item,
            'stock_disponible': total_acumulado,
            'ubicaciones_disponibles': ubicaciones_disponibles
        })
    
    context = {
        'orden': orden,
        'items_info': items_info,
    }
    return render(request, 'almacen/detalle_orden.html', context)

@almacenes_required
@require_POST
def procesar_despacho(request, orden_id):
    """Confirma el despacho de la orden con las cantidades ajustadas."""
    orden = get_object_or_404(SolicitudMaterial, id=orden_id, estado='PENDIENTE')
    data = json.loads(request.body)
    cantidades = data.get('cantidades', {}) # id_movimiento: cantidad
    ubicaciones_seleccionadas = data.get('ubicaciones', {}) # id_movimiento: loc_especifica
    comentarios = data.get('comentarios', '')

    try:
        with transaction.atomic():
            for item in orden.items.all():
                item_id_str = str(item.id)
                nueva_qty = cantidades.get(item_id_str)
                valor_loc = ubicaciones_seleccionadas.get(item_id_str) # "ID|ESPECIFICA"

                if nueva_qty is not None:
                    # Asegurar que usamos punto decimal
                    qty_str = str(nueva_qty).replace(',', '.')
                    item.cantidad = Decimal(qty_str)
                
                # Actualizar la ubicación y sub-ubicación si se especificó
                if valor_loc and "|" in valor_loc:
                    u_id, u_esp = valor_loc.split("|", 1)
                    if u_id:
                        from activos.models import Ubicacion
                        item.ubicacion_origen = Ubicacion.objects.get(id=u_id)
                    item.ubicacion_especifica = u_esp
                
                item.save()
                
                # Liquidar cada ítem
                if item.cantidad > 0:
                    item.liquidar(request.user)
                else:
                    item.estado = 'RECHAZADO'
                    item.save()
            
            orden.estado = 'ENTREGADO'
            orden.entregado_por = request.user
            orden.fecha_entrega = timezone.now()
            orden.comentarios_almacen = comentarios
            orden.save()
            
            return JsonResponse({'success': True, 'message': 'Orden despachada correctamente'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
            

@almacenes_required
@require_POST
def aprobar_solicitud(request, movimiento_id):
    """
    Aprueba una solicitud de movimiento de inventario.
    """
    movimiento = get_object_or_404(MovimientoInventario, id=movimiento_id, estado='PENDIENTE')
    
    try:
        with transaction.atomic():
            movimiento.liquidar(request.user)
        
        messages.success(request, f'Solicitud #{movimiento.id} aprobada exitosamente.')
        return JsonResponse({'success': True, 'message': 'Solicitud aprobada'})
    
    except ValueError as e:
        messages.error(request, f'Error al aprobar solicitud: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    except Exception as e:
        messages.error(request, f'Error inesperado: {str(e)}')
        return JsonResponse({'success': False, 'error': 'Error inesperado'}, status=500)


@almacenes_required
@require_POST
def rechazar_solicitud(request, movimiento_id):
    """
    Rechaza una solicitud de movimiento de inventario.
    """
    movimiento = get_object_or_404(MovimientoInventario, id=movimiento_id, estado='PENDIENTE')
    
    try:
        movimiento.estado = 'RECHAZADO'
        movimiento.aprobado_por = request.user
        movimiento.fecha_aprobacion = timezone.now()
        movimiento.save()
        
        messages.success(request, f'Solicitud #{movimiento.id} rechazada.')
        return JsonResponse({'success': True, 'message': 'Solicitud rechazada'})
    
    except Exception as e:
        messages.error(request, f'Error al rechazar solicitud: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@almacenes_required
def crear_material(request):
    """
    Vista para crear un nuevo material.
    """
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            nombre = request.POST.get('nombre', '').strip()
            sku = request.POST.get('sku', '').strip()
            descripcion = request.POST.get('descripcion', '').strip()
            unidad_medida = request.POST.get('unidad_medida', 'UNIDAD')
            categoria_id = request.POST.get('categoria', None)
            stock_minimo = request.POST.get('stock_minimo', '0')
            
            # Validaciones
            if not nombre:
                messages.error(request, 'El nombre del material es obligatorio.')
                return redirect('almacen:crear_material')
            
            if not sku:
                messages.error(request, 'El SKU es obligatorio.')
                return redirect('almacen:crear_material')
            
            # Verificar que el SKU no exista
            if Material.objects.filter(sku=sku).exists():
                messages.error(request, f'Ya existe un material con el SKU "{sku}".')
                return redirect('almacen:crear_material')
            
            # Crear el material
            material = Material.objects.create(
                nombre=nombre,
                sku=sku,
                descripcion=descripcion,
                categoria_id=categoria_id if categoria_id else None,
                unidad_medida=unidad_medida,
                stock_minimo=float(stock_minimo)
            )
            
            messages.success(request, f'Material "{material.nombre}" creado exitosamente con SKU {material.sku}.')
            return redirect('almacen:crear_material')
        
        except ValueError as e:
            messages.error(request, f'Error en los datos numéricos: {str(e)}')
            return redirect('almacen:crear_material')
        
        except Exception as e:
            messages.error(request, f'Error al crear material: {str(e)}')
            return redirect('almacen:crear_material')
    
    # GET request - mostrar formulario
    unidades_medida = Material.UNIDAD_CHOICES
    categorias = CategoriaMaterial.objects.all()
    ultimos_materiales = Material.objects.all().select_related('categoria').order_by('-creado_en')[:10]
    
    context = {
        'unidades_medida': unidades_medida,
        'categorias': categorias,
        'ultimos_materiales': ultimos_materiales,
    }
    
    return render(request, 'almacen/crear_material.html', context)


@almacenes_required
def detalle_solicitud(request, movimiento_id):
    """
    Vista detallada de una solicitud de movimiento.
    """
    movimiento = get_object_or_404(
        MovimientoInventario.objects.select_related(
            'material', 'usuario', 'ubicacion_origen', 'ubicacion_destino', 
            'orden_trabajo', 'aprobado_por'
        ),
        id=movimiento_id
    )
    
    # Obtener stock actual del material
    stock_total = movimiento.material.get_stock_total()
    
    # Si es salida o traslado, verificar stock en origen
    stock_origen = None
    if movimiento.ubicacion_origen:
        stock_record = StockRecord.objects.filter(
            material=movimiento.material,
            ubicacion=movimiento.ubicacion_origen
        ).first()
        stock_origen = stock_record.cantidad if stock_record else 0
    
    context = {
        'movimiento': movimiento,
        'stock_total': stock_total,
        'stock_origen': stock_origen,
    }
    
    return render(request, 'almacen/detalle_solicitud.html', context)


@almacenes_required
def lista_almacenes(request):
    """
    Lista de ubicaciones que tienen existencias (almacenes).
    """
    # Obtener IDs de ubicaciones con stock
    ubicaciones_con_stock = StockRecord.objects.filter(
        cantidad__gt=0
    ).values_list('ubicacion_id', flat=True).distinct()
    
    almacenes = Ubicacion.objects.filter(id__in=ubicaciones_con_stock).annotate(
        total_items=Count('inventario', filter=Q(inventario__cantidad__gt=0))
    ).order_by('nombre')
    
    return render(request, 'almacen/almacenes.html', {'almacenes': almacenes})


@almacenes_required
def detalle_almacen(request, ubicacion_id):
    """
    Lista de materiales y cantidades en un almacén específico agrupados por ubicación exacta.
    """
    almacen = get_object_or_404(Ubicacion, id=ubicacion_id)
    
    # Filtros
    q = request.GET.get('q', '')
    cat_id = request.GET.get('categoria', '')
    marca_id = request.GET.get('marca', '')
    
    existencias_qs = StockRecord.objects.filter(
        ubicacion=almacen,
        cantidad__gt=0
    ).select_related('material', 'material__categoria', 'material__marca').order_by('ubicacion_especifica', 'material__nombre')
    
    if q:
        existencias_qs = existencias_qs.filter(
            Q(material__nombre__icontains=q) | Q(material__sku__icontains=q)
        )
    
    if cat_id:
        existencias_qs = existencias_qs.filter(material__categoria_id=cat_id)
        
    if marca_id:
        existencias_qs = existencias_qs.filter(material__marca_id=marca_id)
    
    # Agrupar por ubicación específica
    from collections import defaultdict
    agrupados = defaultdict(list)
    for ex in existencias_qs:
        loc = ex.ubicacion_especifica if ex.ubicacion_especifica else "Sin Ubicación"
        agrupados[loc].append(ex)
    
    # Convertir a lista de dicts para el template
    existencias_agrupadas = []
    for loc, items in agrupados.items():
        existencias_agrupadas.append({
            'ubicacion': loc,
            'items': items
        })
    
    # Ordenar por ubicación (Sin Ubicación al final si se desea, o alfabético)
    existencias_agrupadas.sort(key=lambda x: (x['ubicacion'] == "Sin Ubicación", x['ubicacion']))

    categorias = CategoriaMaterial.objects.all()
    marcas = Marca.objects.all().order_by('nombre')
    
    context = {
        'almacen': almacen,
        'existencias_agrupadas': existencias_agrupadas,
        'categorias': categorias,
        'marcas': marcas,
        'q': q,
        'cat_id': int(cat_id) if cat_id else None,
        'marca_id': int(marca_id) if marca_id else None,
    }
    
    return render(request, 'almacen/detalle_almacen.html', context)


@almacenes_required
def asignar_materiales(request):
    """
    Asigna materiales a un almacén (Entrada de inventario).
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ubicacion_id = data.get('ubicacion_id')
            items = data.get('items', [])
            
            if not ubicacion_id:
                return JsonResponse({'success': False, 'error': 'Ubicación no seleccionada'}, status=400)
            
            ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
            
            with transaction.atomic():
                for item in items:
                    material_id = item.get('material_id')
                    cantidad = item.get('cantidad')
                    comentarios = item.get('comentarios', '')
                    
                    if not material_id or not cantidad:
                        continue
                        
                    material = get_object_or_404(Material, id=material_id)
                    loc_esp = item.get('ubicacion_especifica', '').strip().upper()
                    
                    # Crear movimiento de ENTRADA
                    mov = MovimientoInventario.objects.create(
                        material=material,
                        tipo='ENTRADA',
                        cantidad=Decimal(str(cantidad)),
                        ubicacion_destino=ubicacion,
                        ubicacion_especifica=loc_esp,
                        usuario=request.user,
                        comentarios=comentarios
                    )
                    # Liquidar inmediatamente para cargar stock
                    mov.liquidar(request.user)
            
            messages.success(request, f"Se han cargado {len(items)} materiales exitosamente.")
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    # GET: Mostrar formulario
    # Solo ubicaciones de tipo 'OTRO' (Almacenes/Bodegas)
    ubicaciones = Ubicacion.objects.filter(tipo='OTRO').order_by('nombre')
    materiales = Material.objects.all().order_by('nombre')
    
    context = {
        'ubicaciones': ubicaciones,
        'materiales': materiales,
    }
    return render(request, 'almacen/asignar_materiales.html', context)
