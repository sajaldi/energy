from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from .models import Material, StockRecord, MovimientoInventario, SolicitudMaterial, Lote, UnidadMedida, FotoMaterial
from django.db import transaction
from mantenimiento.models import OrdenTrabajo
from activos.models import Ubicacion, Categoria
from .cart_utils import Cart
import json
import time
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from core.decorators import mobile_permission_required
from django.core.files.storage import default_storage
from celery.result import AsyncResult
from .tasks import import_materiales_task
from django.views.decorators.csrf import csrf_exempt
from .models import CategoriaMaterial
from .utils_n8n import notify_n8n_solicitud_material

@login_required
def inventario_dashboard(request):
    """
    Menú interactivo y centro de control para la aplicación de Inventarios.
    """
    from activos.models import Ubicacion
    from .models import CategoriaMaterial
    
    # Datos para el menú/dashboard
    from django.db.models import Q
    ubicaciones = Ubicacion.objects.filter(Q(tipo='BODEGA') | Q(es_almacen=True)).order_by('nombre')
    categorias = CategoriaMaterial.objects.all().order_by('nombre')
    
    # Estadísticas rápidas
    total_materiales = Material.objects.count()
    pedidos_pendientes = SolicitudMaterial.objects.count()
    
    # Verificar si el usuario es del grupo Almacenes o Superusuario
    es_almacen = request.user.groups.filter(name='Almacenes').exists() or request.user.is_superuser
    
    context = {
        'ubicaciones': ubicaciones,
        'categorias': categorias,
        'total_materiales': total_materiales,
        'pedidos_pendientes': pedidos_pendientes,
        'es_almacen': es_almacen,
        'title': 'Gestión de Inventarios'
    }
    return render(request, 'inventarios/dashboard.html', context)

@login_required
def crear_solicitud_dashboard(request):
    """
    Dashboard premium para crear una Solicitud de Materiales con el selector 
    exacto de la Requisición.
    """
    from django.db.models import Q
    ubicaciones = Ubicacion.objects.filter(Q(tipo='BODEGA') | Q(es_almacen=True)).order_by('nombre')
    categorias = CategoriaMaterial.objects.all().order_by('nombre')
    
    # Obtener OTs activas para el buscador inicial
    # Las demás se buscan vía AJAX
    ordenes_recientes = OrdenTrabajo.objects.filter(
        estado__in=['PROGRAMADA', 'EJECUCION']
    ).order_by('-id')[:5]

    context = {
        'ubicaciones': ubicaciones,
        'categorias': categorias,
        'ordenes_recientes': ordenes_recientes,
        'title': 'Crear Solicitud de Materiales'
    }
    return render(request, 'inventarios/crear_solicitud.html', context)
@login_required
def registrar_salida_view(request):
    """
    Interfaz visual premium para registrar salidas de inventario.
    """
    # Categorías para el sidebar
    categorias = Categoria.objects.filter(padre=None).prefetch_related('subcategorias')
    
    # Filtrado por categoría
    cat_id = request.GET.get('categoria')
    materiales_qs = Material.objects.all().prefetch_related('existencias', 'existencias__ubicacion')
    
    if cat_id:
        # Relacionar material -> modelos_compatibles -> modelo -> categoria
        materiales_qs = materiales_qs.filter(modelos_compatibles__modelo__categoria_id=cat_id).distinct()

    materiales = materiales_qs
    # ordenes_activas = OrdenTrabajo.objects.filter(estado__in=['PROGRAMADA', 'EJECUCION']).select_related('ubicacion')
    ubicaciones = Ubicacion.objects.all()

    if request.method == 'POST':
        material_id = request.POST.get('material')
        cantidad = request.POST.get('cantidad')
        ubicacion_id = request.POST.get('ubicacion_origen')
        ot_id = request.POST.get('orden_trabajo')
        comentarios = request.POST.get('comentarios', '')

        try:
            material = get_object_or_404(Material, id=material_id)
            ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
            ot = OrdenTrabajo.objects.filter(id=ot_id).first() if ot_id else None
            dc_cantidad = Decimal(str(cantidad))

            # Verificar stock disponible en la ubicación
            stock_record = StockRecord.objects.filter(material=material, ubicacion=ubicacion).first()
            available = stock_record.cantidad if stock_record else 0
            
            if available < dc_cantidad:
                messages.error(request, f"Error: Stock insuficiente en {ubicacion.nombre}. Disponible: {available} {material.unidad_medida}.")
                return redirect('inventarios:registrar_salida')

            # Crear movimiento de salida
            MovimientoInventario.objects.create(
                material=material,
                tipo='SALIDA',
                cantidad=dc_cantidad,
                cantidad_solicitada=dc_cantidad, # Capturar pedido original
                ubicacion_origen=ubicacion,
                orden_trabajo=ot,
                usuario=request.user,
                comentarios=comentarios
            )
            messages.success(request, f"Solicitud registrada correctamente. El movimiento de {dc_cantidad} quedan PENDIENTES de liquidación por el almacén.")
            return redirect('registrar_salida')
        except Exception as e:
            messages.error(request, f"Error al registrar salida: {str(e)}")

    context = {
        'materiales': materiales,
        # 'ordenes_activas': ordenes_activas,
        'ubicaciones': ubicaciones,
        'categorias': categorias,
        'cat_id': int(cat_id) if cat_id else None,
    }
    return render(request, 'inventarios/registrar_salida.html', context)

@login_required
def api_get_material_stock(request, material_id):
    """
    Retorna los niveles de stock por ubicación para un material dado,
    incluyendo detalles completos del material.
    """
    material = get_object_or_404(Material, id=material_id)
    
    # Obtener stock detallado por ubicación
    existencias = material.existencias.select_related('ubicacion').values(
        'ubicacion__nombre', 'cantidad', 'ubicacion_especifica'
    )
    
    image_url = ""
    if hasattr(material, 'imagen') and material.imagen:
        image_url = material.imagen.url
    else:
        # SVG de respaldo
        image_url = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 24 24' fill='none' stroke='%233b82f6' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z'%3E%3C/path%3E%3Cpolyline points='3.27 6.96 12 12.01 20.73 6.96'%3E%3C/polyline%3E%3Cline x1='12' y1='22.08' x2='12' y2='12'%3E%3C/line%3E%3C/svg%3E"

    # Obtener últimos movimientos
    from .models import MovimientoInventario
    movimientos = MovimientoInventario.objects.filter(material=material).order_by('-fecha_movimiento')[:10]
    
    return JsonResponse({
        'id': material.id,
        'nombre': material.nombre,
        'sku': material.sku,
        'marca': material.marca.nombre if material.marca else "N/A",
        'descripcion': material.descripcion or "Sin descripción disponible.",
        'categoria': material.categoria.nombre if material.categoria else "GENERAL",
        'unidad': material.unidad_medida.nombre if material.unidad_medida else "Unidad",
        'precio_estimado': float(material.precio_estimado),
        'stock_minimo': float(material.stock_minimo),
        'tipo_material': material.get_tipo_material_display() if hasattr(material, 'get_tipo_material_display') else "N/A",
        'image_url': image_url,
        'stock_total': float(material.get_stock_total()),
        'categoria_id': material.categoria_id,
        'unidad_id': material.unidad_medida_id,
        'tipo_raw': material.tipo_material,
        'tipos_choices': [{'id': c[0], 'label': c[1]} for c in Material.TIPO_MATERIAL_CHOICES],
        'existencias': [
            {
                'ubicacion': e['ubicacion__nombre'],
                'cantidad': float(e['cantidad']),
                'detalle': e['ubicacion_especifica'] or ""
            } for e in existencias
        ],
        'movimientos': [
            {
                'fecha': m.fecha_movimiento.strftime('%d/%m/%Y %H:%M'),
                'tipo': m.get_tipo_display(),
                'tipo_raw': m.tipo,
                'cantidad': float(m.cantidad),
                'usuario': m.usuario.get_full_name() or m.usuario.username,
                'ubicacion': m.ubicacion_destino.nombre if m.tipo == 'ENTRADA' else (m.ubicacion_origen.nombre if m.ubicacion_origen else "N/A")
            } for m in movimientos
        ]
    })

@csrf_exempt
@login_required
def api_update_material_mobile(request, material_id):
    """
    API para actualizar los datos técnicos de un material desde la App.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    try:
        # Soportar tanto JSON como FormData (para fotos)
        if request.content_type == 'application/json':
            import json
            data = json.loads(request.body)
        else:
            data = request.POST

        material = get_object_or_404(Material, id=material_id)
        
        material.nombre = data.get('nombre', material.nombre)
        material.sku = data.get('sku', material.sku)
        material.descripcion = data.get('descripcion', material.descripcion)
        
        raw_min = data.get('stock_minimo')
        if raw_min is not None:
            material.stock_minimo = Decimal(str(raw_min))
            
        material.tipo_material = data.get('tipo_material', material.tipo_material)
        
        cat_id = data.get('categoria_id')
        if cat_id:
            material.categoria_id = int(cat_id)
            
        uni_id = data.get('unidad_id')
        if uni_id:
            material.unidad_medida_id = int(uni_id)
            
        # Manejo de Foto Nueva
        if request.FILES.get('imagen'):
            material.imagen = request.FILES['imagen']
            
        material.save()
        return JsonResponse({
            'status': 'success', 
            'message': 'Material actualizado correctamente',
            'new_image_url': material.imagen.url if material.imagen else None
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def cart_add(request):
    """Agrega o actualiza un material en el carrito."""
    if request.method == 'POST':
        data = json.loads(request.body)
        material_id = data.get('material_id')
        cantidad = data.get('cantidad', 1)
        cart = Cart(request)
        cart.add(material_id, cantidad, override_quantity=True)
        return JsonResponse({'status': 'success', 'cart_count': len(cart)})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def cart_remove(request, material_id):
    """Elimina un material del carrito."""
    cart = Cart(request)
    cart.remove(material_id)
    return JsonResponse({'status': 'success', 'cart_count': len(cart)})

@login_required
def cart_detail_view(request):
    """Vista del carrito de compras."""
    cart = Cart(request)
    items = cart.get_items()
    ubicaciones = Ubicacion.objects.all()
    # ordenes_activas = OrdenTrabajo.objects.filter(estado__in=['PROGRAMADA', 'EJECUCION'])
    
    return render(request, 'inventarios/detalle_carrito.html', {
        'items': items,
        'ubicaciones': ubicaciones,
        # 'ordenes_activas': ordenes_activas,
        'cart_count': len(cart)
    })

@login_required
@csrf_exempt
def cart_checkout(request):
    """Procesa el carrito o una lista JSON y crea una orden de salida."""
    if request.method == 'POST':
        # Soporte para JSON y Form Data
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
            except:
                data = {}
        else:
            data = request.POST

        ajax_mode = data.get('ajax_mode') == 'true'
        items_json = data.get('items_json')
        
        ubicacion_id = data.get('ubicacion_origen')
        ot_id = data.get('orden_trabajo')
        comentarios = data.get('comentarios', '')
        edificio_id = data.get('edificio_destino')
        nivel_id = data.get('nivel_destino')
        
        items_to_process = []
        
        if items_json:
            # Procesar desde JSON (Dashboard nuevo)
            try:
                raw_items = json.loads(items_json)
                for ri in raw_items:
                    raw_qty = ri.get('cantidad')
                    if raw_qty is None or raw_qty == "":
                        continue
                    try:
                        qty = Decimal(str(raw_qty))
                    except:
                        continue
                        
                    if qty <= 0:
                        continue
                    mat = get_object_or_404(Material, id=ri['material_id'])
                    items_to_process.append({
                        'material': mat,
                        'quantity': qty
                    })
            except Exception as e:
                if ajax_mode: return JsonResponse({'status': 'error', 'message': f'JSON inválido: {str(e)}'}, status=400)
                messages.error(request, "Datos de materiales inválidos.")
                return redirect('inventarios:cart_detail')
        else:
            # Procesar desde el Carrito de sesión (Vista anterior)
            cart = Cart(request)
            items_to_process = cart.get_items()

        if not items_to_process:
            if ajax_mode: return JsonResponse({'status': 'error', 'message': 'No hay materiales seleccionados.'}, status=400)
            messages.error(request, "El carrito está vacío.")
            return redirect('inventarios:cart_detail')
            
        if not ubicacion_id:
            if ajax_mode: return JsonResponse({'status': 'error', 'message': 'Selecciona una ubicación de origen.'}, status=400)
            messages.error(request, "Debes seleccionar una ubicación de origen.")
            return redirect('inventarios:cart_detail')

        try:
            ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
            ot = OrdenTrabajo.objects.filter(id=ot_id).first() if ot_id else None
            edificio = Ubicacion.objects.filter(id=edificio_id).first() if edificio_id else None
            nivel = Ubicacion.objects.filter(id=nivel_id).first() if nivel_id else None
            
            with transaction.atomic():
                # Crear la cabecera de la orden
                solicitud = SolicitudMaterial.objects.create(
                    usuario=request.user,
                    orden_trabajo=ot,
                    ubicacion_origen=ubicacion,
                    edificio_destino=edificio,
                    nivel_destino=nivel,
                    comentarios_solicitud=comentarios
                )

                # Crear los movimientos asociados
                for item in items_to_process:
                    qty = Decimal(str(item['quantity']))
                    MovimientoInventario.objects.create(
                        solicitud=solicitud,
                        material=item['material'],
                        tipo='SALIDA',
                        cantidad=qty,
                        cantidad_solicitada=qty, # Capturar pedido original
                        ubicacion_origen=ubicacion,
                        orden_trabajo=ot,
                        fecha_aprobacion=None,
                        usuario=request.user,
                        comentarios=comentarios
                    )
            
            # Notificar a n8n (Webhook)
            notify_n8n_solicitud_material(solicitud)
            # Limpiar carrito solo si venimos de la vista de carrito
            if not items_json:
                Cart(request).clear()

            msg = f"Orden #{solicitud.id} registrada correctamente con {len(items_to_process)} ítems."
            if ajax_mode:
                return JsonResponse({'status': 'success', 'message': msg, 'solicitud_id': solicitud.id})
            
            messages.success(request, msg)
            return redirect('inventarios:crear_solicitud')
            
        except Exception as e:
            msg = f"Error en el proceso: {str(e)}"
            if ajax_mode:
                return JsonResponse({'status': 'error', 'message': msg}, status=500)
            messages.error(request, msg)
            return redirect('inventarios:cart_detail')
            
    return redirect('inventarios:cart_detail')

@login_required
def api_get_material_by_sku(request):
    """
    Busca un material por su SKU y retorna su stock actual.
    """
    sku = request.GET.get('sku')
    if not sku:
        return JsonResponse({'status': 'error', 'message': 'SKU no proporcionado'}, status=400)
    
    material = Material.objects.filter(sku=sku).first()
    
    # Si no lo encuentra por SKU, intentar por ID si es numérico
    if not material and sku.isdigit():
        material = Material.objects.filter(id=int(sku)).first()

    if not material:
        return JsonResponse({'status': 'error', 'message': f'Material con código "{sku}" no encontrado'}, status=404)
    
    existencias = material.existencias.select_related('ubicacion').values(
        'ubicacion_id', 'ubicacion__nombre', 'cantidad'
    )
    
    return JsonResponse({
        'id': material.id,
        'nombre': material.nombre,
        'sku': material.sku,
        'unidad': material.unidad_medida,
        'descripcion': material.descripcion or '',
        'precio': float(material.precio_estimado),
        'existencias': list(existencias)
    })

@login_required
def api_registrar_movimiento_rapido(request):
    """
    Registra un movimiento de inventario de forma rápida vía AJAX.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            material_id = data.get('material_id')
            tipo = data.get('tipo') # 'ENTRADA' o 'SALIDA'
            cantidad = Decimal(str(data.get('cantidad', 0)))
            ubicacion_id = data.get('ubicacion_id')
            comentarios = data.get('comentarios', 'Registro desde Escáner')

            if cantidad <= 0:
                return JsonResponse({'status': 'error', 'message': 'La cantidad debe ser mayor a cero'}, status=400)

            material = get_object_or_404(Material, id=material_id)
            ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)

            if tipo == 'SALIDA':
                stock_record = StockRecord.objects.filter(material=material, ubicacion=ubicacion).first()
                available = stock_record.cantidad if stock_record else 0
                if available < cantidad:
                    return JsonResponse({'status': 'error', 'message': f'Stock insuficiente ({available})'}, status=400)

            mov = MovimientoInventario.objects.create(
                material=material,
                tipo=tipo,
                cantidad=cantidad,
                ubicacion_origen=ubicacion if tipo == 'SALIDA' else None,
                ubicacion_destino=ubicacion if tipo == 'ENTRADA' else None,
                usuario=request.user,
                comentarios=comentarios
            )

            return JsonResponse({
                'status': 'success', 
                'message': f'Movimiento de {tipo} registrado correctamente. Pendiente de liquidación.',
                'movimiento_id': mov.id
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required
def scanner_view(request):
    """Vista principal del escáner de inventario."""
    ubicaciones = Ubicacion.objects.all()
    return render(request, 'inventarios/escanear.html', {
        'ubicaciones': ubicaciones
    })

@login_required
@mobile_permission_required('logistica')
def mobile_lista_pedidos(request):
    """Listado móvil de solicitudes de material para el usuario actual."""
    pedidos = SolicitudMaterial.objects.filter(usuario=request.user).order_by('-fecha_solicitud')
    return render(request, 'inventarios/mobile_lista_pedidos.html', {'pedidos': pedidos})

@login_required
def api_pedidos_pendientes_almacen(request):
    """
    Retorna la lista de pedidos pendientes para el modal de Gestión de Salidas.
    """
    if not (request.user.groups.filter(name='Almacenes').exists() or request.user.is_superuser):
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)
        
    pedidos = SolicitudMaterial.objects.filter(estado='PENDIENTE').select_related('usuario', 'orden_trabajo', 'ubicacion_origen').order_by('fecha_solicitud')
    
    data = []
    for p in pedidos:
        data.append({
            'id': p.id,
            'solicitante': p.solicitante_nombre,
            'fecha': p.fecha_solicitud.strftime('%d/%m/%Y %H:%M'),
            'ot': str(p.orden_trabajo.id) if p.orden_trabajo else 'N/A',
            'almacen': p.ubicacion_origen.nombre if p.ubicacion_origen else 'N/A',
            'items_count': p.items.count(),
            'comentarios': p.comentarios_solicitud or ''
        })
    return JsonResponse({'status': 'success', 'pedidos': data, 'count': len(data)})

@login_required
def api_detalle_solicitud_almacen(request, pk):
    """Retorna los items (movimientos) de una solicitud pendiente para el almacenista."""
    if not (request.user.groups.filter(name='Almacenes').exists() or request.user.is_superuser):
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)
    
    solicitud = get_object_or_404(SolicitudMaterial, pk=pk)
    items = solicitud.items.select_related('material', 'material__unidad_medida').all()
    
    data = []
    for mov in items:
        m = mov.material
        image_url = m.imagen.url if m.imagen else ''
        stock_actual = m.get_stock_total()
        data.append({
            'mov_id': mov.id,
            'material_id': m.id,
            'nombre': m.nombre,
            'sku': m.sku,
            'unidad': m.unidad_medida.nombre if m.unidad_medida else 'Unidad',
            'cantidad_solicitada': float(mov.cantidad),
            'stock_disponible': float(stock_actual),
            'image_url': image_url
        })
    
    return JsonResponse({
        'status': 'success',
        'solicitud': {
            'id': solicitud.id,
            'solicitante': solicitud.solicitante_nombre,
            'fecha': solicitud.fecha_solicitud.strftime('%d/%m/%Y %H:%M'),
            'comentarios': solicitud.comentarios_solicitud or '',
            'almacen': solicitud.ubicacion_origen.nombre if solicitud.ubicacion_origen else 'N/A'
        },
        'items': data
    })

@csrf_exempt
@login_required
def api_despachar_solicitud(request, pk):
    """Despacha (aprueba) o rechaza una solicitud de material."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    if not (request.user.groups.filter(name='Almacenes').exists() or request.user.is_superuser):
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)
    
    solicitud = get_object_or_404(SolicitudMaterial, pk=pk)
    
    try:
        data = json.loads(request.body)
    except:
        data = {}
    
    accion = data.get('accion', 'despachar')
    comentarios_almacen = data.get('comentarios', '')
    
    from django.utils import timezone
    
    if accion == 'rechazar':
        solicitud.estado = 'RECHAZADO'
        solicitud.comentarios_almacen = comentarios_almacen
        solicitud.save()
        # Rechazar todos los movimientos pendientes
        solicitud.items.filter(estado='PENDIENTE').update(estado='RECHAZADO')
        return JsonResponse({'status': 'success', 'message': f'Solicitud #{solicitud.id} rechazada.'})
    
    # Despachar: Liquidar cada movimiento con cantidades ajustadas
    cantidades_map = {}
    for c in data.get('cantidades', []):
        cantidades_map[int(c['mov_id'])] = Decimal(str(c['cantidad']))
    
    errores = []
    procesados = 0
    
    with transaction.atomic():
        for mov in solicitud.items.filter(estado='PENDIENTE'):
            try:
                # Si el almacenista especificó cantidad para este movimiento
                cantidad_entregada = cantidades_map.get(mov.id, mov.cantidad)
                
                if cantidad_entregada <= 0:
                    # No entregar este item, dejarlo pendiente o rechazarlo
                    mov.estado = 'RECHAZADO'
                    mov.comentarios = (mov.comentarios or '') + f' | No entregado por almacén.'
                    mov.save()
                    continue
                
                # Actualizar cantidad del movimiento a lo que el almacenista realmente entrega
                mov.cantidad = cantidad_entregada
                mov.save()
                
                mov.liquidar(request.user)
                procesados += 1
            except ValueError as e:
                errores.append(f"{mov.material.nombre}: {str(e)}")
        
        if not errores:
            solicitud.estado = 'ENTREGADO'
            solicitud.fecha_entrega = timezone.now()
            solicitud.entregado_por = request.user
            solicitud.comentarios_almacen = comentarios_almacen
            solicitud.save()

        # Notificar éxito vía Webhook a n8n para que avise al técnico
        from .utils_n8n import notify_n8n_despacho_material
        notify_n8n_despacho_material(solicitud)
    
    if errores:
        return JsonResponse({
            'status': 'partial',
            'message': f'Se procesaron {procesados} ítems, pero hubo errores.',
            'errores': errores
        }, status=400)
    
    return JsonResponse({'status': 'success', 'message': f'Solicitud #{solicitud.id} despachada exitosamente. {procesados} ítems entregados.'})

@login_required
@mobile_permission_required('logistica')
def mobile_detalle_pedido(request, pk):
    """Detalle móvil de una solicitud de material."""
    pedido = get_object_or_404(SolicitudMaterial, pk=pk, usuario=request.user)
    items = pedido.items.select_related('material', 'material__unidad_medida').all()
    
    # Asegurar que para ítems antiguos cantidad_solicitada != 0 en el contexto si es necesario,
    # aunque lo manejaremos mejor en el template con el filtro |default
    
    return render(request, 'inventarios/mobile_detalle_pedido.html', {
        'pedido': pedido,
        'items': items
    })

@login_required
@mobile_permission_required('logistica')
# Vista movil para crear solicitudes
def mobile_crear_solicitud(request):
    """Interfaz móvil para crear solicitudes de material."""
    from activos.models import Ubicacion
    from .models import CategoriaMaterial
    from mantenimiento.models import OrdenTrabajo
    from django.db.models import Q
    
    ubicaciones = Ubicacion.objects.filter(Q(tipo='BODEGA') | Q(es_almacen=True)).order_by('nombre')
    categorias = CategoriaMaterial.objects.all().order_by('nombre')
    edificios = Ubicacion.objects.filter(tipo='EDIFICIO').order_by('nombre')
    
    # Contexto para el selector de OTs en móviles (pueden ser las 10 más recientes)
    ordenes_recientes = OrdenTrabajo.objects.filter(
        estado__in=['PROGRAMADA', 'EJECUCION']
    ).order_by('-id')[:10]

    return render(request, 'inventarios/mobile_crear_solicitud.html', {
        'ubicaciones': ubicaciones,
        'categorias': categorias,
        'edificios': edificios,
        'ordenes_recientes': ordenes_recientes,
        'title': 'Nueva Solicitud'
    })

@login_required
@mobile_permission_required('logistica')
def mobile_inventario_dashboard(request):
    """
    Dashboard móvil optimizado para la gestión de materiales e inventarios.
    Funciona como Hub central para el Almacenista.
    """
    from activos.models import Ubicacion
    from .models import CategoriaMaterial, Material, SolicitudMaterial, MovimientoInventario
    from django.db.models import Q
    
    # Estadísticas rápidas
    total_materiales = Material.objects.count()
    pedidos_pendientes = SolicitudMaterial.objects.filter(estado='PENDIENTE').count()
    
    # Discrepancias (movimientos inconsistentes aprobados)
    discrepancias = MovimientoInventario.objects.filter(es_inconsistente=True, estado='APROBADO').select_related('material', 'ubicacion_origen').order_by('-fecha_movimiento')
    discrepancias_count = discrepancias.count()
    
    # Verificar si el usuario es del grupo Almacenes o Superusuario
    es_almacen = request.user.groups.filter(name='Almacenes').exists() or request.user.is_superuser
    
    # Datos para el alta de material
    categorias = CategoriaMaterial.objects.all().order_by('nombre')
    unidades = UnidadMedida.objects.all().order_by('nombre')
    # Se amplía el filtro para incluir Bodegas y Almacenes
    ubicaciones = Ubicacion.objects.filter(
        Q(tipo='ALMACEN') | Q(tipo='BODEGA') | Q(es_almacen=True)
    ).order_by('nombre')
    
    context = {
        'total_materiales': total_materiales,
        'pedidos_pendientes': pedidos_pendientes,
        'discrepancias_count': discrepancias_count,
        'discrepancias_list': discrepancias[:10], # Mostrar últimas 10 en el dashboard
        'es_almacen': es_almacen,
        'title': 'Gestión de Materiales',
        'is_almacen': es_almacen, # Alias para el template
        'categorias': categorias,
        'unidades': unidades,
        'ubicaciones': ubicaciones,
    }
    return render(request, 'inventarios/mobile_dashboard.html', context)

@login_required
@mobile_permission_required('logistica')
def mobile_historial_movimientos(request):
    """
    Vista móvil para ver el historial de entradas, salidas y traslados de material.
    """
    from .models import MovimientoInventario
    
    # Obtener los últimos 100 movimientos de inventario
    movimientos = MovimientoInventario.objects.select_related(
        'material', 'usuario', 'ubicacion_origen', 'ubicacion_destino'
    ).order_by('-fecha_movimiento')[:100]
    
    context = {
        'movimientos': movimientos,
        'title': 'Historial de Movimientos'
    }
    return render(request, 'inventarios/mobile_movimientos.html', context)

@login_required
@mobile_permission_required('gestion_almacen')
def mobile_gestion_salidas_view(request):
    """
    Vista móvil para que el almacenista gestione las salidas de material (solicitudes pendientes).
    """
    # Verificar si el usuario es del grupo Almacenes o Superusuario
    es_almacen = request.user.groups.filter(name='Almacenes').exists() or request.user.is_superuser
    
    if not es_almacen:
        return redirect('inventarios:dashboard')

    # Obtener el número de pedidos pendientes para el contador inicial
    pedidos_pendientes = SolicitudMaterial.objects.filter(estado='PENDIENTE').count()
    
    context = {
        'pedidos_pendientes': pedidos_pendientes,
        'title': 'Gestión de Salidas'
    }
    return render(request, 'inventarios/mobile_gestion_salidas.html', context)

@login_required
def api_niveles_por_edificio(request):
    """Devuelve los niveles/pisos hijos de un edificio."""
    from activos.models import Ubicacion
    from django.http import JsonResponse

    edificio_id = request.GET.get('edificio_id')
    if not edificio_id:
        return JsonResponse({'results': []})

    niveles = Ubicacion.objects.filter(padre_id=edificio_id).order_by('orden', 'nombre')
    results = [{'id': n.id, 'nombre': n.nombre, 'tipo': n.tipo} for n in niveles]
    
    # También chequear si el padre mismo ya tiene QR
    parent = Ubicacion.objects.get(id=edificio_id)
    has_qr = bool(parent.codigo_qr)
    
    return JsonResponse({'results': results, 'parent_has_qr': has_qr})

@login_required
def api_search_ordenes_trabajo(request):
    """API para buscar Órdenes de Trabajo activas."""
    from mantenimiento.models import OrdenTrabajo
    from django.http import JsonResponse
    from django.db.models import Q

    q = request.GET.get('q', '').strip()
    ots = OrdenTrabajo.objects.filter(
        estado__in=['ESPERA', 'PROGRAMADA', 'EJECUCION']
    ).select_related('rutina', 'aviso', 'ubicacion').order_by('-id')

    if q:
        ots = ots.filter(
            Q(codigo_de_orden__icontains=q) |
            Q(descripcion_corta__icontains=q) |
            Q(rutina__nombre__icontains=q) |
            Q(aviso__descripcion__icontains=q) |
            Q(ubicacion__nombre__icontains=q)
        )

    ots = ots[:20]

    results = []
    # Usar prefetch o select_related no alcanza fácil para jerarquía profunda, 
    # pero resolvemos con queries cacheados o subiendo.
    for ot in ots:
        nombre = ot.rutina.nombre if ot.rutina else (
            ot.aviso.descripcion[:50] if ot.aviso else (ot.descripcion_corta or 'OT Correctiva')
        )
        ubicacion_nombre = ot.ubicacion.nombre if ot.ubicacion else 'S/U'
        
        edificio_id = None
        nivel_id = None
        
        if ot.ubicacion:
            curr = ot.ubicacion
            visited = set()
            while curr and curr.id not in visited:
                visited.add(curr.id)
                if curr.tipo == 'NIVEL' and not nivel_id:
                    nivel_id = curr.id
                elif curr.tipo == 'EDIFICIO' and not edificio_id:
                    edificio_id = curr.id
                curr = curr.padre

        results.append({
            'id': ot.id,
            'codigo': ot.codigo_de_orden or f'OT-{ot.id}',
            'nombre': nombre,
            'ubicacion': ubicacion_nombre,
            'edificio_id': edificio_id,
            'nivel_id': nivel_id,
            'estado': ot.get_estado_display(),
            'tipo': ot.get_tipo_display(),
        })

    return JsonResponse({'results': results})

@staff_member_required
def import_materiales_background(request):
    """Renders the upload form for background import."""
    from django.contrib import admin
    context = {
        **admin.site.each_context(request),
        'title': 'Importación masiva de Materiales (Background)',
    }
    return render(request, 'admin/inventarios/material/import_background.html', context)

@staff_member_required
@csrf_exempt
def import_materiales_process(request):
    """Triggers the Celery task for importing materials."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    is_confirm = request.POST.get('confirm', '').lower() in ['true', 'on', '1']
    existing_path = request.POST.get('file_path')
    import_file = request.FILES.get('import_file')

    # Si NO es confirmación, necesitamos un archivo nuevo obligatoriamente
    if not is_confirm:
        if not import_file:
            return JsonResponse({'error': 'No se subió ningún archivo'}, status=400)
            
        file_ext = import_file.name.split('.')[-1].lower()
        temp_name = f'tmp/import_materiales_{request.user.id}_{int(time.time())}.{file_ext}'
        
        try:
            path = default_storage.save(temp_name, import_file)
        except Exception as e:
            return JsonResponse({'error': f'Error al guardar archivo: {str(e)}'}, status=500)
    else:
        # ES UNA CONFIRMACIÓN: Usar el archivo que ya está en el servidor
        if not existing_path:
            return JsonResponse({'error': 'Falta la ruta del archivo para confirmar'}, status=400)
        path = existing_path
        file_ext = path.split('.')[-1].lower()
    
    # Limpiar cache de progreso anterior para este usuario
    cache_key = f"import_materiales_progress_{request.user.id}"
    cache.delete(cache_key)
    
    # Trigger Celery task
    v_val = request.POST.get('verification_mode', '').lower()
    verification_mode = v_val in ['true', 'on', '1']
    
    # Lógica de Dry Run: SOLO si no es verificación y no es confirmación final
    dry_run = (not verification_mode) and (not is_confirm)
    
    task = import_materiales_task.delay(
        path, 
        file_ext, 
        user_id=request.user.id, 
        verification_mode=verification_mode,
        dry_run=dry_run
    )
    
    return JsonResponse({
        'status': 'started', 
        'task_id': task.id, 
        'dry_run': dry_run,
        'verification_mode': verification_mode
    })

@staff_member_required
def import_materiales_progress(request):
    """API to poll progress for material import."""
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'error': 'Falta task_id'}, status=400)
        
    cache_key = f"import_materiales_progress_{request.user.id}"
    progress = cache.get(cache_key, {'status': 'pending', 'percent': 0})
    
    res = AsyncResult(task_id)
    progress['state'] = res.state if res else 'PENDING'
    
    if res.state == 'SUCCESS':
        if isinstance(res.result, dict):
            progress.update(res.result)
        progress['state'] = 'COMPLETED'
        progress['percent'] = 100
    elif res.state == 'FAILURE':
        progress['error'] = str(res.result)
        progress['state'] = 'FAILURE'
        
    return JsonResponse(progress)

@login_required
def imprimir_etiquetas_view(request):
    """Vista para seleccionar materiales y cantidades para etiquetas."""
    from django.contrib import admin
    context = {
        **admin.site.each_context(request),
        'title': 'Impresión de Etiquetas',
    }
    return render(request, 'inventarios/imprimir_etiquetas.html', context)

@login_required
def generar_pdf_etiquetas(request):
    """Genera el PDF con las etiquetas seleccionadas."""
    import io
    import qrcode
    import base64
    from django.http import HttpResponse
    from django.template.loader import get_template
    from xhtml2pdf import pisa
    from django.urls import reverse
    
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)

    # getlist returns list of material IDs
    material_ids = request.POST.getlist('materials[]')
    if not material_ids:
        return HttpResponse('No materials selected', status=400)

    # Pre-fetch materials
    materials = Material.objects.filter(id__in=material_ids).select_related('categoria')
    materials_map = {str(m.id): m for m in materials}

    labels_data = []

    for mid in material_ids:
        qty_key = f'qty_{mid}'
        quantity_str = request.POST.get(qty_key, '1')
        try:
            quantity = int(quantity_str)
        except ValueError:
            quantity = 1
        
        material = materials_map.get(str(mid))
        if not material: 
            continue

        # Generar QR
        try:
             # Try to get absolute URL if get_absolute_url is defined, otherwise fallback
             if hasattr(material, 'get_absolute_url'):
                 url = material.get_absolute_url()
             else:
                 # Assuming standard admin url pattern
                 url = reverse('admin:inventarios_material_change', args=[material.id])
                 
             link = request.build_absolute_uri(url)
        except:
             link = str(material.id)
        
        qr = qrcode.QRCode(version=1, box_size=10, border=0)
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        # Procesar imagen del material si existe
        img_b64 = None
        if material.imagen:
            try:
                # Abrir imagen desde el storage
                with material.imagen.open('rb') as f:
                    img_data = f.read()
                    img_b64 = base64.b64encode(img_data).decode('utf-8')
            except Exception:
                pass

        # Repetir la etiqueta según la cantidad solicitada
        for _ in range(quantity):
            labels_data.append({
                'sku': material.sku,
                'nombre': material.nombre,
                'unidad': material.unidad_medida.nombre if material.unidad_medida else 'Unidad',
                'ubicacion': 'General', 
                'qr_code': qr_b64,
                'image_data': img_b64
            })
    
    # Contexto para el template
    context = {'labels': labels_data}
    template = get_template('inventarios/etiquetas_pdf.html')
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    # inline para ver en navegador, attachment para descargar
    response['Content-Disposition'] = 'inline; filename="etiquetas.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse(f'Error generating PDF: {pisa_status.err}', status=500)
        
    return response
@login_required
def master_catalog(request):
    """
    Vista para el catálogo maestro visual en formato de tarjetas (cuadritos).
    """
    from activos.models import Ubicacion
    from django.db.models import Q
    
    categorias = CategoriaMaterial.objects.all().order_by('nombre')
    ubicaciones = Ubicacion.objects.filter(Q(tipo='BODEGA') | Q(es_almacen=True)).order_by('nombre')
    
    context = {
        'categorias': categorias,
        'ubicaciones': ubicaciones,
        'title': 'Catálogo Maestro'
    }
    return render(request, 'inventarios/master_catalog.html', context)

@login_required
def mobile_catalog(request):
    """
    Vista optimizada para celular del catálogo maestro.
    Agrupa por categorías y permite filtrar por almacén.
    """
    from activos.models import Ubicacion
    from django.db.models import Q
    
    categorias = CategoriaMaterial.objects.all().order_by('nombre')
    ubicaciones = Ubicacion.objects.filter(Q(tipo='BODEGA') | Q(es_almacen=True)).order_by('nombre')
    
    context = {
        'categorias': categorias,
        'ubicaciones': ubicaciones,
        'title': 'Catálogo de Repuestos'
    }
    return render(request, 'inventarios/mobile_catalog.html', context)
@login_required
def api_print_label(request, material_id):
    import io
    import base64
    import qrcode
    from xhtml2pdf import pisa
    from django.template.loader import get_template
    from django.urls import reverse
    
    material = get_object_or_404(Material, id=material_id)
    quantity = int(request.GET.get('qty', 1))
    
    # El usuario pide que el QR sea el código (SKU)
    qr_data = material.sku
    
    qr = qrcode.QRCode(version=1, box_size=3, border=1) # QR más pequeño para etiqueta pequeña
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    # Procesar imagen del material
    img_b64 = None
    if material.imagen:
        try:
            with material.imagen.open('rb') as f:
                img_data = f.read()
                img_b64 = base64.b64encode(img_data).decode('utf-8')
        except:
            pass

    labels_data = []
    for _ in range(quantity):
        labels_data.append({
            'sku': material.sku,
            'nombre': material.nombre,
            'unidad': material.unidad_medida.nombre if material.unidad_medida else 'Unidad',
            'ubicacion': 'General', 
            'qr_code': qr_b64,
            'image_data': img_b64
        })
    
    context = {'labels': labels_data}
    template = get_template('inventarios/etiquetas_pdf.html')
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="etiqueta_{material.sku}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse(f'Error generating PDF: {pisa_status.err}', status=500)
        
    return response
@login_required
@csrf_exempt
def api_ingreso_lote(request):
    if request.method == 'POST':
        try:
            # Soporte para multipart/form-data (para fotos) o JSON
            if request.content_type.startswith('multipart/form-data'):
                items_raw = request.POST.get('items', '[]')
                items = json.loads(items_raw)
                ubicacion_id = request.POST.get('ubicacion_destino')
                comentarios = request.POST.get('comentarios', 'Ingreso por lote')
                requisicion_id = request.POST.get('requisicion_id')
            else:
                data = json.loads(request.body)
                items = data.get('items', [])
                ubicacion_id = data.get('ubicacion_destino')
                comentarios = data.get('comentarios', 'Ingreso por lote')
                requisicion_id = data.get('requisicion_id')
            
            if not ubicacion_id or not items:
                return JsonResponse({'status': 'error', 'message': 'Datos incompletos'}, status=400)
                
            ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
            
            # Buscamos la requisición si se proporcionó un ID
            requisicion_obj = None
            if requisicion_id:
                from presupuestos.models import Requisicion
                # Intentamos buscar por ID interno o por cr8ca_requisicionid
                requisicion_obj = Requisicion.objects.filter(cr8ca_requisicionid=requisicion_id).first()
                if not requisicion_obj and str(requisicion_id).isdigit():
                    requisicion_obj = Requisicion.objects.filter(id=int(requisicion_id)).first()

            with transaction.atomic():
                # 1. Creamos la cabecera del ingreso para trazabilidad
                from inventarios.models import IngresoInventario, FotoIngreso
                ingreso_header = IngresoInventario.objects.create(
                    usuario=request.user,
                    ubicacion_destino=ubicacion,
                    requisicion_origen=requisicion_obj,
                    comentarios=comentarios
                )

                # 2. Guardamos las fotos si vienen en el request
                fotos = request.FILES.getlist('fotos')
                for f in fotos:
                    FotoIngreso.objects.create(
                        ingreso=ingreso_header,
                        imagen=f
                    )

                for item in items:
                    material = get_object_or_404(Material, id=item['id'])
                    cantidad = Decimal(str(item.get('quantity', 0)))
                    lote_codigo = item.get('lote')
                    comentario_item = item.get('comentario', '')
                    
                    if cantidad <= 0: continue

                    lote_obj = None
                    if lote_codigo and str(lote_codigo).strip():
                        lote_obj, _ = Lote.objects.get_or_create(
                            material=material,
                            codigo=lote_codigo.strip()
                        )
                    
                    comentario_final = comentario_item if comentario_item else comentarios

                    from django.utils import timezone
                    MovimientoInventario.objects.create(
                        material=material,
                        tipo='ENTRADA',
                        cantidad=cantidad,
                        lote=lote_obj,
                        ubicacion_destino=ubicacion,
                        usuario=request.user,
                        comentarios=comentario_final,
                        ingreso=ingreso_header,
                        estado='APROBADO',
                        aprobado_por=request.user,
                        fecha_aprobacion=timezone.now()
                    )
            
            return JsonResponse({'status': 'success', 'message': 'Ingreso registrado correctamente', 'ingreso_id': ingreso_header.id})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
@login_required
def api_list_solicitudes(request):
    from django.db.models import Q
    from presupuestos.models import Requisicion
    query = request.GET.get('q', '')
    
    # Buscamos en Requisiciones de la app presupuestos
    requisiciones = Requisicion.objects.all().order_by('-fecha')
    
    if query:
        requisiciones = requisiciones.filter(
            Q(cr8ca_requisicion__icontains=query) |
            Q(cr8ca_asunto__icontains=query) |
            Q(usuario_solicitante__username__icontains=query) |
            Q(usuario_solicitante__first_name__icontains=query)
        )
    
    results = []
    for r in requisiciones[:20]:
        solicitante = r.usuario_solicitante.get_full_name() if r.usuario_solicitante else "Desconocido"
        fecha_str = r.fecha.strftime('%d/%m/%y') if r.fecha else "S/F"
        count = r.articulos.count()
        results.append({
            'id': str(r.cr8ca_requisicionid),
            'text': f"{r.cr8ca_requisicion} | {solicitante} | {fecha_str}",
            'asunto': r.cr8ca_asunto or "Sin asunto",
            'count': count
        })
    return JsonResponse({'results': results})

@login_required
def api_get_solicitud_items(request, pk):
    from presupuestos.models import Requisicion
    # El pk aquí será el UUID cr8ca_requisicionid
    requisicion = get_object_or_404(Requisicion, cr8ca_requisicionid=pk)
    items = []
    
    for item in requisicion.articulos.all():
        m = item.material
        if m:
            image_url = m.imagen.url if m.imagen else "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 24 24' fill='none' stroke='%233b82f6' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z'%3E%3C/path%3E%3Cpolyline points='3.27 6.96 12 12.01 20.73 6.96'%3E%3C/polyline%3E%3Cline x1='12' y1='22.08' x2='12' y2='12'%3E%3C/line%3E%3C/svg%3E"
            items.append({
                'id': m.id,
                'nombre': m.nombre,
                'sku': m.sku,
                'cantidad': float(item.cr8ca_cantidad),
                'unidad': m.unidad_medida.nombre if m.unidad_medida else 'Unidad',
                'image_url': image_url
            })
        else:
            # Si el artículo no está vinculado a un material del catálogo, 
            # podrías manejarlo aquí, pero el dashboard de inventario necesita materiales reales.
            pass
            
    return JsonResponse({'items': items})

@csrf_exempt
@login_required
def api_create_material(request):
    """
    Crea un nuevo material desde un modal rápido en el dashboard.
    Maneja FormData (archivos y texto) y opcionalmente añade un stock inicial.
    Funciona offline gracias al CSFR_Exempt, asumiendo session cookie válida.
    """
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre')
            sku = request.POST.get('sku')
            descripcion = request.POST.get('descripcion', '')
            categoria_id = request.POST.get('categoria_id')
            unidad_id = request.POST.get('unidad_id')
            
            stock_inicial = request.POST.get('stock_inicial')
            ubicacion_id = request.POST.get('ubicacion_id')
            # Las fotos pueden venir como 'imagen' (compatible con antes) o 'fotos' (múltiples)
            fotografias = request.FILES.getlist('fotos')
            imagen_principal = request.FILES.get('imagen')
            
            if not nombre or not sku:
                return JsonResponse({'status': 'error', 'message': 'El Nombre y SKU son obligatorios.'}, status=400)
                
            if Material.objects.filter(sku=sku).exists():
                return JsonResponse({'status': 'error', 'message': f'El SKU {sku} ya existe en el sistema.'}, status=400)
                
            with transaction.atomic():
                # Crear Material
                material = Material.objects.create(
                    nombre=nombre.strip(),
                    sku=sku.strip(),
                    descripcion=descripcion.strip()
                )
                
                if categoria_id:
                    material.categoria_id = categoria_id
                if unidad_id:
                    material.unidad_medida_id = unidad_id
                
                # Imagen principal
                if imagen_principal:
                    material.imagen = imagen_principal
                elif fotografias:
                    material.imagen = fotografias[0] # Usar la primera como principal
                
                material.save()

                # Guardar fotos adicionales
                from .models import FotoMaterial
                for f in fotografias:
                    FotoMaterial.objects.create(material=material, imagen=f)
                    
                # Crear stock inicial si aplica
                if stock_inicial and ubicacion_id:
                    cantidad = Decimal(stock_inicial)
                    if cantidad > 0:
                        ubicacion = Ubicacion.objects.get(id=ubicacion_id)
                        
                        MovimientoInventario.objects.create(
                            material=material,
                            tipo='ENTRADA',
                            cantidad=cantidad,
                            ubicacion_destino=ubicacion,
                            estado='APROBADO',
                            usuario=request.user,
                            comentarios="Inventario/Stock Inicial (Carga Rápida/Offline)"
                        )

            return JsonResponse({
                'status': 'success',
                'message': 'Material creado correctamente.',
                'material': {
                    'id': material.id,
                    'nombre': material.nombre,
                    'sku': material.sku
                }
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required
def api_get_material_by_sku(request):
    """Retorna información detallada de un material por su SKU."""
    sku = request.GET.get('sku', '').strip()
    if not sku:
        return JsonResponse({'status': 'error', 'message': 'SKU no proporcionado'}, status=400)
    
    material = Material.objects.filter(sku=sku).select_related('unidad_medida').first()
    if not material:
        return JsonResponse({'status': 'error', 'message': 'Material no encontrado'}, status=404)
    
    # Obtener existencias actuales
    existencias = []
    for sr in material.existencias.all():
        existencias.append({
            'ubicacion': sr.ubicacion.nombre,
            'cantidad': float(sr.cantidad)
        })
    
    # Obtener últimos 10 movimientos (Ficha de movimientos)
    from .models import MovimientoInventario
    movimientos_objs = MovimientoInventario.objects.filter(material=material).order_by('-fecha_movimiento')[:10]
    movimientos_list = []
    for m in movimientos_objs:
        # Resolver ubicación para mostrar
        ubi = "N/A"
        if m.tipo == 'ENTRADA':
            ubi = m.ubicacion_destino.nombre if m.ubicacion_destino else "N/A"
        elif m.tipo == 'SALIDA':
            ubi = m.ubicacion_origen.nombre if m.ubicacion_origen else "N/A"
        elif m.tipo == 'AJUSTE':
            ubi = m.ubicacion_origen.nombre if m.ubicacion_origen else "Ajuste"
        
        movimientos_list.append({
            'id': m.id,
            'tipo': m.get_tipo_display(),
            'tipo_raw': m.tipo,
            'cantidad': float(m.cantidad),
            'fecha': m.fecha_movimiento.strftime('%d/%m/%y %H:%M'),
            'ubicacion': ubi,
            'usuario': m.usuario.get_full_name() or m.usuario.username if m.usuario else "Sistema",
            'comentarios': m.comentarios or ""
        })

    return JsonResponse({
        'status': 'success',
        'id': material.id,
        'nombre': material.nombre,
        'sku': material.sku,
        'unidad': material.unidad_medida.nombre if material.unidad_medida else 'Unidad',
        'existencias': existencias,
        'movimientos': movimientos_list,
        'imagen': material.imagen.url if material.imagen else None
    })

@csrf_exempt
@login_required
def api_registrar_movimiento_rapido(request):
    """
    API para registrar movimientos de entrada, salida o ajuste desde el escáner.
    Implementa el workflow: 1. Sacar, 2. Ingresar, 3. Ajustar.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        material_id = data.get('material_id')
        tipo = data.get('tipo') # ENTRADA, SALIDA, AJUSTE
        cantidad = Decimal(str(data.get('cantidad', 0)))
        ubicacion_id = data.get('ubicacion_id')
        comentarios = data.get('comentarios', 'Movimiento rápido desde escáner')
        
        material = get_object_or_404(Material, id=material_id)
        ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
        
        with transaction.atomic():
            if tipo == 'AJUSTE':
                # El ajuste corrige el stock al valor indicado (cantidad)
                # Obtenemos stock actual en esa ubicación
                stock_record = StockRecord.objects.filter(material=material, ubicacion=ubicacion).first()
                stock_actual = stock_record.cantidad if stock_record else Decimal('0')
                delta = cantidad - stock_actual
                
                if delta == 0:
                    return JsonResponse({'status': 'success', 'message': 'No se requiere ajuste, el stock ya es correcto.'})
                
                final_tipo = 'ENTRADA' if delta > 0 else 'SALIDA'
                final_qty = abs(delta)
            else:
                final_tipo = tipo
                final_qty = cantidad

            mov = MovimientoInventario.objects.create(
                material=material,
                tipo=final_tipo,
                cantidad=final_qty,
                ubicacion_destino=ubicacion if final_tipo == 'ENTRADA' else None,
                ubicacion_origen=ubicacion if final_tipo == 'SALIDA' else None,
                usuario=request.user,
                comentarios=comentarios + (' (Ajuste automático)' if tipo == 'AJUSTE' else ''),
                estado='APROBADO' # Auto-aprobado para carga rápida
            )
            mov.liquidar(request.user)
            
        return JsonResponse({'status': 'success', 'message': f'Movimiento de {tipo} registrado correctamente.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def pwa_manifest(request):
    """
    Retorna el manifest.json dinámico para la PWA de Inventarios.
    """
    manifest = {
        "name": "Gestión de Inventarios",
        "short_name": "Inventario",
        "description": "Aplicación de SoftCoM para control de bodega y existencias.",
        "start_url": "/inventarios/",
        "display": "standalone",
        "background_color": "#f8fafc",
        "theme_color": "#1e293b",
        "orientation": "portrait",
        "icons": [
            {
                "src": "/static/core/img/icon-512.png",
                "sizes": "192x192 512x512",
                "type": "image/png"
            }
        ]
    }
    return JsonResponse(manifest)

@csrf_exempt
@login_required
def api_create_material(request):
    """
    API robusta para el alta de material desde dispositivos móviles.
    Soporta múltiples fotos y el ingreso del stock inicial con auto-liquidación.
    """
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre')
            sku = request.POST.get('sku')
            categoria_id = request.POST.get('categoria_id')
            unidad_id = request.POST.get('unidad_id')
            ubicacion_id = request.POST.get('ubicacion_id')
            
            # Robustecer parseo de stock_inicial
            raw_stock = request.POST.get('stock_inicial', '0')
            try:
                stock_inicial = Decimal(raw_stock) if raw_stock and raw_stock.strip() else Decimal('0')
            except (ValueError, InvalidOperation, NameError):
                stock_inicial = Decimal('0')

            if not nombre or not sku:
                return JsonResponse({'status': 'error', 'message': 'Nombre y SKU son obligatorios'}, status=400)

            # Limpiar IDs de FKs (evitar strings vacíos)
            categoria_id = int(categoria_id) if categoria_id and str(categoria_id).isdigit() else None
            unidad_id = int(unidad_id) if unidad_id and str(unidad_id).isdigit() else None
            ubicacion_id = int(ubicacion_id) if ubicacion_id and str(ubicacion_id).isdigit() else None

            force_update = request.POST.get('force_update') == 'true'
            
            # 1. Comprobar existencia previa para detectar conflictos
            existing_material = Material.objects.filter(sku=sku).first()
            
            if existing_material and not force_update:
                return JsonResponse({
                    'status': 'conflict',
                    'message': f'El SKU "{sku}" ya está registrado con el nombre "{existing_material.nombre}".',
                    'existing_nombre': existing_material.nombre
                })

            with transaction.atomic():
                if existing_material and force_update:
                    # Actualizar campos
                    existing_material.nombre = nombre
                    if categoria_id: existing_material.categoria_id = categoria_id
                    if unidad_id: existing_material.unidad_medida_id = unidad_id
                    existing_material.save()
                    material = existing_material
                    created = False
                else:
                    # Crear nuevo
                    material = Material.objects.create(
                        sku=sku,
                        nombre=nombre,
                        categoria_id=categoria_id if categoria_id else None,
                        unidad_medida_id=unidad_id if unidad_id else None
                    )
                    created = True

                # 2. Procesar Fotos
                fotos = request.FILES.getlist('fotos')
                for f in fotos:
                    FotoMaterial.objects.create(material=material, imagen=f)

                # 3. Stock Inicial
                if stock_inicial > 0 and ubicacion_id:
                    try:
                        ubicacion = Ubicacion.objects.get(id=ubicacion_id)
                        mov = MovimientoInventario.objects.create(
                            material=material,
                            tipo='ENTRADA',
                            cantidad=stock_inicial,
                            ubicacion_destino=ubicacion,
                            usuario=request.user,
                            comentarios=f'Carga inicial ({"Actualización" if force_update else "Sincronización"})'
                        )
                        mov.liquidar(request.user)
                    except Ubicacion.DoesNotExist:
                        if created: # Si lo acabamos de crear, devolver error 400
                             return JsonResponse({'status': 'error', 'message': f'La ubicación ID {ubicacion_id} no existe.'}, status=400)
                        # Si es actualización, solo ignoramos el stock si la ubicación falla

            return JsonResponse({
                'status': 'success', 
                'message': 'Actualizado correctamente' if force_update else 'Sincronizado correctamente',
                'material_id': material.id,
                'created': created
            })

        except Exception as e:
            # Imprimir el error exacto para que el usuario pueda verlo en el log de Django
            import traceback
            traceback.print_exc()
            return JsonResponse({'status': 'error', 'message': f'Error en servidor: {str(e)}'}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

def pwa_sw(request):
    """
    Retorna el Service Worker (sw.js) servido desde el scope de Django.
    Este SW es la clave para la operatividad en el "Sótano" (Sin señal).
    """
    js = """
const CACHE_NAME = 'inventarios-pwa-v2';
const urlsToCache = [
  '/inventarios/mobile/dashboard/',
  '/inventarios/catalogo/',
  '/inventarios/escanear/',
  '/static/core/img/icon-512.png',
  'https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap',
  'https://unpkg.com/ionicons@7.1.0/dist/ionicons/ionicons.esm.js',
  'https://cdn.jsdelivr.net/npm/sweetalert2@11'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
          console.log('SW: Pre-caching App Shell');
          return cache.addAll(urlsToCache);
      })
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// Estrategia: Network-First para navegación, con fallback a caché.
// Esto permite ver el catálogo o dashboard offline si ya se visitaron.
self.addEventListener('fetch', event => {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Para otros recursos (fotos, scripts), Cache-First
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        return response || fetch(event.request);
      })
  );
});

// Background Sync Event
self.addEventListener('sync', event => {
  if (event.tag === 'sync-nuevo-material') {
    event.waitUntil(syncTodo());
  }
});

async function syncTodo() {
  const db = await new Promise((resolve, reject) => {
    const request = indexedDB.open('InventarioPWA', 3);
    request.onerror = () => reject(request.error); 
    request.onsuccess = () => resolve(request.result);
  });

  await syncMateriales(db);
  await syncMovimientos(db);
}

async function syncMateriales(db) {
  const tx = db.transaction('materiales_sync', 'readonly');
  const store = tx.objectStore('materiales_sync');
  const allRecords = await new Promise((resolve, reject) => {
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });

  for (const record of allRecords) {
    try {
      const finalFd = new FormData();
      for (const key in record) {
        if (!['fotos', 'id', 'timestamp'].includes(key) && record[key]) {
          finalFd.append(key, record[key]);
        }
      }
      if (record.fotos && record.fotos.length > 0) {
        record.fotos.forEach(f => {
          finalFd.append('fotos', f.blob, f.name);
        });
      }

      const response = await fetch('/inventarios/api/material/quick-create/', { method: 'POST', body: finalFd });
      if (response.ok) {
          const dTx = db.transaction('materiales_sync', 'readwrite');
          dTx.objectStore('materiales_sync').delete(record.id);
      }
    } catch (err) { console.log('Sync Material Error', err); }
  }
}

async function syncMovimientos(db) {
  const tx = db.transaction('movimientos_sync', 'readonly');
  const store = tx.objectStore('movimientos_sync');
  const allRecords = await new Promise(r => { 
      const req = store.getAll(); req.onsuccess = () => r(req.result);
  });

  for (const record of allRecords) {
    try {
      const response = await fetch('/inventarios/api/movimiento-rapido/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(record.data)
      });
      if (response.ok) {
        const dTx = db.transaction('movimientos_sync', 'readwrite');
        dTx.objectStore('movimientos_sync').delete(record.id);
      }
    } catch (err) { console.log('Sync Movement Error', err); }
  }
}
"""
    return HttpResponse(js, content_type='application/javascript')

@login_required
def api_resolver_discrepancia(request):
    """
    Resuelve una discrepancia de inventario creando un movimiento de AJUSTE.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    import json
    from decimal import Decimal
    try:
        data = json.loads(request.body)
        mov_id = data.get('mov_id')
        conteo_real = Decimal(str(data.get('conteo_real', 0)))
        
        from .models import MovimientoInventario, StockRecord
        mov_original = MovimientoInventario.objects.get(id=mov_id)
        
        # 1. Obtener stock teórico actual en la ubicación de la discrepancia
        stock_actual = Decimal('0')
        sq = StockRecord.objects.get(
            material=mov_original.material,
            ubicacion=mov_original.ubicacion_origen,
            lote=mov_original.lote,
            ubicacion_especifica=mov_original.ubicacion_especifica
        )
        stock_actual = sq.cantidad
    except (MovimientoInventario.DoesNotExist, StockRecord.DoesNotExist):
        # Si no existe StockRecord, asumimos 0
        stock_actual = Decimal('0')
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # 2. Calcular diferencia
    diferencia = conteo_real - stock_actual
    
    if diferencia == 0:
        # Solo limpiar el flag si ya coinciden
        mov_original.es_inconsistente = False
        mov_original.save()
        return JsonResponse({'status': 'success', 'message': 'El stock ya coincide. Discrepancia corregida.'})

    # 3. Crear movimiento de ajuste
    nuevo_ajuste = MovimientoInventario(
        material=mov_original.material,
        tipo='AJUSTE',
        cantidad=abs(diferencia),
        usuario=request.user,
        comentarios=f"Ajuste automático para resolver discrepancia de movimiento #{mov_id}. Conteo real: {conteo_real}",
        lote=mov_original.lote,
        ubicacion_especifica=mov_original.ubicacion_especifica
    )

    if diferencia > 0:
        # Sumar stock: Usar ubicacion_destino
        nuevo_ajuste.ubicacion_destino = mov_original.ubicacion_origen
    else:
        # Restar stock: Usar ubicacion_origen
        nuevo_ajuste.ubicacion_origen = mov_original.ubicacion_origen

    nuevo_ajuste.save()
    nuevo_ajuste.liquidar(request.user)

    # 4. Limpiar flag del original
    mov_original.es_inconsistente = False
    mov_original.save()

    return JsonResponse({
        'status': 'success', 
        'message': f'Ajuste de {diferencia} aplicado correctamente.',
        'nuevo_stock': float(conteo_real)
    })
