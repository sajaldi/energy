from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from decimal import Decimal, InvalidOperation
from django.utils import timezone
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
from presupuestos.models import ArticuloRequisicion
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
    from .models import CategoriaMaterial, Rack
    
    # Datos para el menú/dashboard
    from django.db.models import Q
    ubicaciones = Ubicacion.objects.filter(Q(tipo='BODEGA') | Q(es_almacen=True)).order_by('nombre')
    categorias = CategoriaMaterial.objects.all().order_by('nombre')
    
    # Estadísticas rápidas
    total_materiales = Material.objects.count()
    pedidos_pendientes = SolicitudMaterial.objects.count()
    
    # Verificar si el usuario es del grupo Almacenes o Superusuario
    es_almacen = request.user.groups.filter(name='Almacenes').exists() or request.user.is_superuser
    
    ot_id = request.GET.get('ot_id')
    ot_pre = None
    if ot_id:
        try:
            ot_pre = OrdenTrabajo.objects.get(pk=ot_id)
        except OrdenTrabajo.DoesNotExist:
            pass

    racks = Rack.objects.filter(activo=True).select_related('bodega').order_by('bodega__nombre', 'orden')

    context = {
        'ubicaciones': ubicaciones,
        'categorias': categorias,
        'total_materiales': total_materiales,
        'pedidos_pendientes': pedidos_pendientes,
        'es_almacen': es_almacen,
        'ot_pre': ot_pre,
        'racks': racks,
        'active_tab': 'dashboard',
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
    edificios = Ubicacion.objects.filter(tipo='EDIFICIO').order_by('nombre')
    
    # Obtener OTs activas para el buscador inicial
    # Las demás se buscan vía AJAX
    ordenes_recientes = OrdenTrabajo.objects.filter(
        estado__in=['PROGRAMADA', 'EJECUCION']
    ).order_by('-id')[:10]

    # Clon exacto del formulario móvil (mismo template y contexto)
    context = {
        'ubicaciones': ubicaciones,
        'categorias': categorias,
        'edificios': edificios,
        'ordenes_recientes': ordenes_recientes,
        'title': 'Nueva Solicitud'
    }
    return render(request, 'inventarios/mobile_crear_solicitud.html', context)
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
    from django.db.models import Sum
    material = get_object_or_404(Material, id=material_id)
    
    image_url = ""
    if hasattr(material, 'imagen') and material.imagen:
        image_url = material.imagen.url
    else:
        image_url = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 24 24' fill='none' stroke='%233b82f6' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z'%3E%3C/polyline%3E%3Cpolyline points='3.27 6.96 12 12.01 20.73 6.96'%3E%3C/polyline%3E%3Cline x1='12' y1='22.08' x2='12' y2='12'%3E%3C/line%3E%3C/svg%3E"

    # Una sola consulta para existencias + stock total
    existencias_qs = material.existencias.select_related('ubicacion').values(
        'ubicacion__nombre', 'cantidad', 'ubicacion_especifica'
    )
    existencias = list(existencias_qs)
    stock_total = sum(float(e['cantidad']) for e in existencias)

    # Clasificación de Stock (Nuevo vs Usado) — sin get_stock_total()
    stock_nuevo = Decimal('0.00')
    stock_usado = Decimal('0.00')

    if material.sku.endswith('-USADO'):
        base_sku = material.sku.replace('-USADO', '')
        original = Material.objects.filter(sku=base_sku).first()
        stock_usado = stock_total
        if original:
            stock_nuevo = float(original.existencias.aggregate(total=Sum('cantidad'))['total'] or 0)
    else:
        variant_sku = f"{material.sku}-USADO"
        variant = Material.objects.filter(sku=variant_sku).first()
        stock_nuevo = stock_total
        if variant:
            stock_usado = float(variant.existencias.aggregate(total=Sum('cantidad'))['total'] or 0)

    # Obtener últimos movimientos
    from .models import MovimientoInventario
    movimientos_qs = MovimientoInventario.objects.filter(material=material).select_related(
        'usuario', 'ubicacion_origen', 'ubicacion_destino', 'solicitud', 'solicitud__usuario', 'orden_trabajo', 'devolucion', 'ingreso'
    ).order_by('-fecha_movimiento')
    movimientos = list(movimientos_qs[:15])
    
    # Movimientos pendientes
    pendientes = [m for m in movimientos if m.estado == 'PENDIENTE']
    mov_pendientes = [
        {
            'id': p.id,
            'fecha': p.fecha_movimiento.strftime('%d/%m/%Y %H:%M'),
            'tipo': p.get_tipo_display(),
            'tipo_raw': p.tipo,
            'cantidad': float(p.cantidad),
            'usuario': p.usuario.get_full_name() or p.usuario.username if p.usuario else 'Sistema',
            'ubicacion': (p.ubicacion_destino.nombre if p.ubicacion_destino else "N/A") if p.tipo == 'ENTRADA' else (p.ubicacion_origen.nombre if p.ubicacion_origen else "N/A"),
            'comentarios': p.comentarios or '',
            'solicitud_id': p.solicitud_id,
            'orden_trabajo_info': f"OT {p.orden_trabajo.codigo_de_orden}" if p.orden_trabajo else None,
        } for p in pendientes
    ]
    
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
        'stock_total': stock_total,
        'stock_nuevo': float(stock_nuevo),
        'stock_usado': float(stock_usado),
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
                'id': m.id,
                'fecha': m.fecha_movimiento.strftime('%d/%m/%Y %H:%M'),
                'tipo': 'Devolución' if m.devolucion or (m.comentarios and "Devolución #" in m.comentarios) else m.get_tipo_display(),
                'tipo_raw': m.tipo,
                'cantidad': float(m.cantidad),
                'cantidad_solicitada': float(m.cantidad_solicitada) if m.cantidad_solicitada else None,
                'es_salida': m.tipo == 'SALIDA' or (m.tipo == 'AJUSTE' and m.ubicacion_origen_id and not m.ubicacion_destino_id),
                'usuario': m.usuario.get_full_name() or m.usuario.username if m.usuario else 'Sistema',
                'ubicacion': (m.ubicacion_destino.nombre if m.ubicacion_destino else "N/A") if m.tipo in ['ENTRADA', 'TRASLADO'] else (m.ubicacion_origen.nombre if m.ubicacion_origen else (m.ubicacion_destino.nombre if m.ubicacion_destino else "N/A")),
                'solicitud_id': m.solicitud_id,
                'solicitud_info': f"Orden #{m.solicitud_id} - {m.solicitud.usuario.get_full_name() or m.solicitud.usuario.username}" if m.solicitud else None,
                'orden_trabajo_id': m.orden_trabajo_id,
                'orden_trabajo_info': f"OT #{m.orden_trabajo.codigo_de_orden or m.orden_trabajo_id} - {(m.orden_trabajo.descripcion_corta or '')[:50]}" if m.orden_trabajo else None,
                'comentarios': m.comentarios or '',
                'estado': m.get_estado_display(),
                'estado_raw': m.estado,
            } for m in movimientos
        ],
        'cambios_campos': [
            {
                'fecha': c.fecha.strftime('%d/%m/%Y %H:%M'),
                'usuario': c.usuario.get_full_name() or c.usuario.username if c.usuario else 'Sistema',
                'campo': c.campo,
                'valor_anterior': c.valor_anterior,
                'valor_nuevo': c.valor_nuevo,
            } for c in material.historial_cambios.select_related('usuario').order_by('-fecha')[:20]
        ] if hasattr(material, 'historial_cambios') else [],
        'movimientos_pendientes': mov_pendientes,
        'requisiciones': [
            {
                'id': str(art.cr8ca_itemderequisicionid),
                'requisicion_pk': str(art.requisicion.pk),
                'requisicion_numero': art.requisicion.cr8ca_requisicion,
                'requisicion_asunto': art.requisicion.cr8ca_asunto,
                'estado': art.requisicion.estado_requisicion,
                'fecha': art.requisicion.fecha.strftime('%d/%m/%Y') if art.requisicion.fecha else '',
                'solicitante': art.requisicion.usuario_solicitante.get_full_name() or art.requisicion.usuario_solicitante.username if art.requisicion.usuario_solicitante else '',
                'articulo': art.cr8ca_articulo,
                'cantidad': float(art.cr8ca_cantidad),
                'costo_aproximado': float(art.cr8ca_costoaproximado) if art.cr8ca_costoaproximado else 0,
                'proveedor': art.proveedor.nombre if art.proveedor else '',
            } for art in ArticuloRequisicion.objects.filter(
                material=material
            ).select_related(
                'requisicion',
                'requisicion__usuario_solicitante',
                'proveedor'
            ).order_by('-requisicion__fecha')
        ],
        'activos_utilizados': [
            {
                'activo_id': uso.activo_id,
                'activo_nombre': uso.activo.nombre if uso.activo else 'Sin asignar',
                'activo_codigo': uso.activo.codigo_interno if uso.activo else '',
                'cantidad': float(uso.cantidad),
                'ot_id': uso.orden_trabajo_id,
                'ot_codigo': uso.orden_trabajo.codigo_de_orden or f'OT-{uso.orden_trabajo_id}',
                'ot_tipo': uso.orden_trabajo.get_tipo_display(),
                'comentario': uso.comentario,
                'fecha': uso.fecha_registro.strftime('%d/%m/%Y %H:%M'),
                'registrado_por': uso.registrado_por.get_full_name() if uso.registrado_por else '',
            } for uso in material.usos_en_ot.select_related(
                'activo', 'orden_trabajo', 'registrado_por'
            ).order_by('-fecha_registro')[:30]
        ],
    })

@csrf_exempt
@login_required
def api_update_material_mobile(request, material_id):
    """
    API para actualizar los datos técnicos de un material desde la App.
    Registra cambios en el historial.
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
        from .models import HistorialCambioMaterial
        
        cambios = []
        
        # Nombre
        nuevo_nombre = data.get('nombre', material.nombre)
        if nuevo_nombre != material.nombre:
            cambios.append(('nombre', str(material.nombre), str(nuevo_nombre)))
            material.nombre = nuevo_nombre
        
        # SKU
        nuevo_sku = data.get('sku', material.sku)
        if nuevo_sku != material.sku:
            cambios.append(('sku', str(material.sku), str(nuevo_sku)))
            material.sku = nuevo_sku
        
        # Descripción
        nuevo_desc = data.get('descripcion', material.descripcion)
        if nuevo_desc != material.descripcion:
            cambios.append(('descripcion', str(material.descripcion or ''), str(nuevo_desc or '')))
            material.descripcion = nuevo_desc
        
        # Stock mínimo
        raw_min = data.get('stock_minimo')
        if raw_min is not None:
            nuevo_min = Decimal(str(raw_min))
            if nuevo_min != material.stock_minimo:
                cambios.append(('stock_minimo', str(material.stock_minimo), str(nuevo_min)))
                material.stock_minimo = nuevo_min
        
        # Tipo material
        nuevo_tipo = data.get('tipo_material', material.tipo_material)
        if nuevo_tipo != material.tipo_material:
            cambios.append(('tipo_material', str(material.tipo_material), str(nuevo_tipo)))
            material.tipo_material = nuevo_tipo
        
        # Categoría
        cat_id = data.get('categoria_id')
        if cat_id:
            cat_id = int(cat_id)
            if cat_id != material.categoria_id:
                old_cat = material.categoria.nombre if material.categoria else 'Sin categoría'
                from .models import CategoriaMaterial
                new_cat = CategoriaMaterial.objects.filter(pk=cat_id).values_list('nombre', flat=True).first() or str(cat_id)
                cambios.append(('categoria', old_cat, new_cat))
                material.categoria_id = cat_id
        
        # Unidad de medida
        uni_id = data.get('unidad_id')
        if uni_id:
            uni_id = int(uni_id)
            if uni_id != material.unidad_medida_id:
                old_uni = material.unidad_medida.nombre if material.unidad_medida else 'Sin unidad'
                new_uni = UnidadMedida.objects.filter(pk=uni_id).values_list('nombre', flat=True).first() or str(uni_id)
                cambios.append(('unidad_medida', old_uni, new_uni))
                material.unidad_medida_id = uni_id
        
        # Manejo de Foto Nueva
        if request.FILES.get('imagen'):
            cambios.append(('imagen', 'anterior', 'nueva imagen'))
            material.imagen = request.FILES['imagen']
        
        material.save()
        
        # Guardar historial de cambios
        for campo, anterior, nuevo in cambios:
            HistorialCambioMaterial.objects.create(
                material=material,
                usuario=request.user,
                campo=campo,
                valor_anterior=anterior,
                valor_nuevo=nuevo,
            )
        
        return JsonResponse({
            'status': 'success', 
            'message': f'Material actualizado correctamente ({len(cambios)} campo(s) modificado(s))',
            'new_image_url': material.imagen.url if material.imagen else None,
            'cambios': len(cambios),
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
        ticket_id = data.get('ticket')
        comentarios = data.get('comentarios', '')
        edificio_id = data.get('edificio_destino')
        nivel_id = data.get('nivel_destino')
        entregar_a_id = data.get('entregar_a')
        
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
        
        # Para borradores, la ubicación no es obligatoria
        estado_solicitado = data.get('estado', '')
        es_borrador = estado_solicitado == 'BORRADOR'
        
        if not ubicacion_id and not es_borrador:
            if ajax_mode: return JsonResponse({'status': 'error', 'message': 'Selecciona una ubicación de origen.'}, status=400)
            messages.error(request, "Debes seleccionar una ubicación de origen.")
            return redirect('inventarios:cart_detail')

        # Validar materiales técnicos: requieren una OT o un Ticket vinculado
        if not es_borrador and not ot_id and not ticket_id:
            materiales_tecnicos = [i for i in items_to_process if getattr(i.get('material') if isinstance(i, dict) else i, 'es_tecnico', False)]
            if not materiales_tecnicos:
                # También checar en caso de que items_to_process tenga objetos del cart
                materiales_tecnicos = [i for i in items_to_process if isinstance(i, dict) and i.get('material') and i['material'].es_tecnico]
            if materiales_tecnicos:
                nombres = ", ".join([i['material'].nombre if isinstance(i, dict) else i.material.nombre for i in materiales_tecnicos[:3]])
                msg = f'Los siguientes materiales son técnicos y requieren una Orden de Trabajo o un Ticket vinculado: {nombres}'
                if ajax_mode: return JsonResponse({'status': 'error', 'message': msg}, status=400)
                messages.error(request, msg)
                return redirect('inventarios:cart_detail')

        try:
            ubicacion = Ubicacion.objects.filter(id=ubicacion_id).first() if ubicacion_id else None
            ot = OrdenTrabajo.objects.filter(id=ot_id).first() if ot_id else None
            ticket = None
            if ticket_id:
                from callcenter.models import SolicitudTicket
                ticket = SolicitudTicket.objects.filter(id=ticket_id).first()
            edificio = Ubicacion.objects.filter(id=edificio_id).first() if edificio_id else None
            nivel = Ubicacion.objects.filter(id=nivel_id).first() if nivel_id else None
            entregar_a_user = None
            if entregar_a_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                entregar_a_user = User.objects.filter(id=entregar_a_id).first()
            
            with transaction.atomic():
                # Verificar si el usuario tiene un jefe inmediato
                jefe = getattr(request.user, 'perfil', None) and getattr(request.user.perfil, 'responsable', None)

                # ¿Hay aprobadores de salida en los departamentos de los materiales?
                from core.models import PerfilUsuario as _PU
                from .models import Material as _MatModel
                _materiales_ids = [i['material'].id for i in items_to_process]
                _deptos_ids = set()
                for _mat in _MatModel.objects.filter(id__in=_materiales_ids).prefetch_related('departamentos'):
                    for _depto in _mat.departamentos.all():
                        _deptos_ids.add(_depto.id)
                hay_aprobadores = False
                if _deptos_ids:
                    hay_aprobadores = _PU.objects.filter(
                        departamento_id__in=_deptos_ids, aprobador_salidas=True
                    ).exists()

                # Si se pide guardar como borrador, respetar ese estado.
                # Requiere autorización si hay aprobadores por departamento o jefe directo.
                if es_borrador:
                    estado_inicial = 'BORRADOR'
                elif hay_aprobadores or jefe:
                    estado_inicial = 'PENDIENTE_AUTORIZACION'
                else:
                    estado_inicial = 'PENDIENTE'

                # Crear la cabecera de la orden
                solicitud = SolicitudMaterial.objects.create(
                    usuario=request.user,
                    orden_trabajo=ot,
                    ticket=ticket,
                    ubicacion_origen=ubicacion,
                    edificio_destino=edificio,
                    nivel_destino=nivel,
                    entregar_a=entregar_a_user,
                    comentarios_solicitud=comentarios,
                    estado=estado_inicial
                )

                # Crear los movimientos asociados (no para borradores)
                if not es_borrador:
                    for item in items_to_process:
                        qty = Decimal(str(item['quantity']))
                        MovimientoInventario.objects.create(
                            solicitud=solicitud,
                            material=item['material'],
                            tipo='SALIDA',
                            cantidad=qty,
                            cantidad_solicitada=qty,
                            ubicacion_origen=ubicacion,
                            orden_trabajo=ot,
                            fecha_aprobacion=None,
                            usuario=request.user,
                            comentarios=comentarios
                    )
            
            # Notificaciones (solo si no es borrador)
            if estado_inicial != 'BORRADOR':
                if estado_inicial == 'PENDIENTE_AUTORIZACION':
                    # Determinar quién debe aprobar:
                    # 1. Si algún material tiene departamentos permitidos → notificar a los aprobadores de salida de esos departamentos
                    # 2. Si no, notificar al jefe directo (flujo original)
                    from core.models import PerfilUsuario as PU
                    materiales_ids = [i['material'].id for i in items_to_process]
                    from .models import Material as MatModel
                    deptos_con_aprobadores = set()
                    for mat in MatModel.objects.filter(id__in=materiales_ids).prefetch_related('departamentos'):
                        for depto in mat.departamentos.all():
                            deptos_con_aprobadores.add(depto.id)
                    
                    if deptos_con_aprobadores:
                        # Buscar aprobadores de salida en esos departamentos
                        aprobadores = PU.objects.filter(
                            departamento_id__in=deptos_con_aprobadores,
                            aprobador_salidas=True
                        ).select_related('usuario')
                        
                        if aprobadores.exists():
                            from .utils_ntfy import notificar_aprobadores_salida
                            notificar_aprobadores_salida(solicitud, aprobadores)
                        else:
                            # Fallback: jefe directo
                            from .utils_ntfy import notificar_pendiente_aprobacion
                            notificar_pendiente_aprobacion(solicitud)
                    else:
                        # Sin departamentos restringidos → jefe directo
                        from .utils_ntfy import notificar_pendiente_aprobacion
                        notificar_pendiente_aprobacion(solicitud)
                else:
                    # Push notification vía ntfy al almacén
                    from .utils_ntfy import notificar_nueva_solicitud
                    notificar_nueva_solicitud(solicitud)
                # Webhook a Power Automate
                from .utils_n8n import notify_powerautomate_solicitud
                notify_powerautomate_solicitud(solicitud)
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
        
        # Detalle de ubicaciones
        existencias = m.existencias.select_related('ubicacion').filter(cantidad__gt=0)
        ubicaciones = [
            {'nombre': ex.ubicacion.nombre, 'cantidad': float(ex.cantidad), 'detalle': ex.ubicacion_especifica or ''}
            for ex in existencias
        ]

        # Verificar stock usado (SKU-USADO)
        sku_usado = f"{m.sku}-USADO"
        # Intentamos buscar el material usado
        material_usado = Material.objects.filter(sku=sku_usado).first()
        stock_usado = float(material_usado.get_stock_total()) if material_usado else 0

        data.append({
            'mov_id': mov.id,
            'material_id': m.id,
            'nombre': m.nombre,
            'sku': m.sku,
            'unidad': m.unidad_medida.nombre if m.unidad_medida else 'Unidad',
            'cantidad_solicitada': float(mov.cantidad),
            'stock_disponible': float(stock_actual),
            'stock_usado': stock_usado,
            'ubicaciones': ubicaciones,
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
    
    # Manejar tanto JSON puro como FormData (para fotos)
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except:
            data = {}
    else:
        # Asumimos multipart/form-data
        data = request.POST.dict()
        if 'cantidades' in data:
            data['cantidades'] = json.loads(data['cantidades'])
    
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
    
    # Procesar Fotos si las hay
    from .models import FotoDespacho
    photos = request.FILES.getlist('fotos')
    for p in photos:
        FotoDespacho.objects.create(solicitud=solicitud, imagen=p)
    
    # Despachar: Liquidar cada movimiento con cantidades ajustadas
    cantidades_map = {}
    for c in data.get('cantidades', []):
        cantidades_map[int(c['mov_id'])] = {
            'cantidad': Decimal(str(c.get('cantidad', 0))),
            'cantidad_usada': Decimal(str(c.get('cantidad_usada', 0)))
        }
    
    errores = []
    procesados = 0
    
    with transaction.atomic():
        for mov in solicitud.items.filter(estado='PENDIENTE'):
            try:
                # Obtener lo que el almacenista especificó
                item_data = cantidades_map.get(mov.id, {'cantidad': mov.cantidad, 'cantidad_usada': 0})
                cant_nueva = item_data['cantidad']
                cant_usada = item_data['cantidad_usada']
                
                if cant_nueva <= 0 and cant_usada <= 0:
                    # No entregar este item, rechazarlo
                    mov.estado = 'RECHAZADO'
                    mov.comentarios = (mov.comentarios or '') + f' | No entregado por almacén.'
                    mov.save()
                    continue
                
                # Caso 1: Se entrega material USADO
                if cant_usada > 0:
                    # Buscar el material usado
                    sku_usado = f"{mov.material.sku}-USADO"
                    material_usado = Material.objects.filter(sku=sku_usado).first()
                    if not material_usado:
                        errores.append(f"{mov.material.nombre}: No existe registro de material USADO para este SKU.")
                        continue
                    
                    # Si se entrega TODO como usado, simplemente cambiamos el material del movimiento original
                    # Si se entrega PARCIAL, creamos un nuevo movimiento para el usado
                    if cant_nueva == 0:
                        mov.material = material_usado
                        mov.cantidad = cant_usada
                        mov.save()
                        mov.liquidar(request.user)
                        procesados += 1
                    else:
                        # Entrega Mixta: El original se queda como nuevo, creamos uno nuevo para el usado
                        mov_usado = MovimientoInventario.objects.create(
                            material=material_usado,
                            tipo=mov.tipo,
                            cantidad=cant_usada,
                            ubicacion_origen=mov.ubicacion_origen,
                            ubicacion_destino=mov.ubicacion_destino,
                            usuario=mov.usuario,
                            solicitud=mov.solicitud,
                            estado='PENDIENTE', # Se liquida ahora
                            comentarios=f"Entrega de material usado (Sustitución de {mov.material.nombre})"
                        )
                        mov_usado.liquidar(request.user)
                        
                        # Actualizar el original con la parte nueva
                        mov.cantidad = cant_nueva
                        mov.save()
                        mov.liquidar(request.user)
                        procesados += 2 # Contamos ambos como procesados
                
                # Caso 2: Solo se entrega material NUEVO (comportamiento original)
                elif cant_nueva > 0:
                    mov.cantidad = cant_nueva
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

        # Notificar a Power Automate
        from .utils_n8n import notify_powerautomate_despacho
        notify_powerautomate_despacho(solicitud)
    
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
    """Detalle móvil de una solicitud de material.

    Puede verlo: el dueño de la solicitud, alguien del mismo departamento del
    solicitante, un aprobador de salidas o el personal de Almacenes. Así los
    enlaces del correo (autorización, despacho) funcionan para todos.
    """
    pedido = get_object_or_404(SolicitudMaterial, pk=pk)

    perfil = getattr(request.user, 'perfil', None)
    mi_departamento_id = getattr(getattr(perfil, 'departamento', None), 'id', None)
    sol_perfil = getattr(pedido.usuario, 'perfil', None)
    sol_departamento_id = getattr(getattr(sol_perfil, 'departamento', None), 'id', None)

    es_dueno = pedido.usuario_id == request.user.id
    mismo_departamento = bool(mi_departamento_id and mi_departamento_id == sol_departamento_id)
    es_aprobador = bool(perfil and getattr(perfil, 'aprobador_salidas', False))
    es_almacen_grp = request.user.groups.filter(name__iexact='Almacenes').exists()

    if not (es_dueno or mismo_departamento or es_aprobador or es_almacen_grp or request.user.is_superuser):
        return HttpResponse("No tienes permiso para ver esta solicitud.", status=403)

    items = pedido.items.select_related('material', 'material__unidad_medida').all()

    for item in items:
        m = item.material
        item.image_url = m.imagen.url if m.imagen else ''

    es_almacen = es_almacen_grp
    puede_despachar = es_almacen and pedido.estado == 'PENDIENTE'
    puede_confirmar_entrega = es_almacen and pedido.estado == 'LISTO_RECOLECCION'

    # Personas autorizadas para aprobar los materiales de esta solicitud
    try:
        from .utils_n8n import _obtener_aprobadores_solicitud
        jefe_directo = getattr(sol_perfil, 'responsable', None) if sol_perfil else None
        jefe_departamento = None
        if sol_perfil and getattr(sol_perfil, 'departamento', None):
            jefe_departamento = getattr(sol_perfil.departamento, 'responsable', None)
        superior = jefe_directo or jefe_departamento
        aprobadores = _obtener_aprobadores_solicitud(pedido, superior)
    except Exception:
        aprobadores = []

    return render(request, 'inventarios/mobile_detalle_pedido.html', {
        'pedido': pedido,
        'items': items,
        'puede_despachar': puede_despachar,
        'puede_confirmar_entrega': puede_confirmar_entrega,
        'es_almacen': es_almacen,
        'aprobadores': aprobadores,
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
@require_POST
def api_crear_ot_rapida(request):
    """Crea una OT rápida desde la solicitud de material (sin ubicación/activos)."""
    from mantenimiento.models import OrdenTrabajo
    from django.utils import timezone
    from datetime import timedelta
    import json
    
    try:
        data = json.loads(request.body)
        descripcion = data.get('descripcion', '').strip()
        if not descripcion:
            return JsonResponse({'status': 'error', 'message': 'La descripción es obligatoria.'}, status=400)
        
        ot = OrdenTrabajo.objects.create(
            tipo='CORRECTIVA',
            estado='EJECUCION',
            prioridad='MEDIA',
            tecnico=request.user,
            descripcion_corta=descripcion,
            inicio_programado=timezone.now(),
            fin_programado=timezone.now() + timedelta(hours=4),
            notas=f"Creada desde solicitud de material por {request.user.get_full_name() or request.user.username}"
        )
        
        return JsonResponse({
            'status': 'success',
            'ot_id': ot.id,
            'ot_codigo': ot.codigo_de_orden or f'OT-{ot.id}',
            'ot_descripcion': descripcion,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
def api_enviar_borrador(request, pk):
    """Cambia una solicitud de BORRADOR a PENDIENTE y dispara notificaciones."""
    solicitud = get_object_or_404(SolicitudMaterial, pk=pk, usuario=request.user)
    
    if solicitud.estado != 'BORRADOR':
        return JsonResponse({'status': 'error', 'message': 'Solo se pueden enviar solicitudes en borrador.'}, status=400)
    
    if not solicitud.ubicacion_origen:
        return JsonResponse({'status': 'error', 'message': 'Seleccione una bodega de origen antes de enviar.'}, status=400)
    
    # Crear movimientos si no existen (antes de calcular aprobadores, que dependen
    # de los materiales asociados a la solicitud)
    from decimal import Decimal
    if not solicitud.items.filter(tipo='SALIDA').exists():
        for item in solicitud.items.all():
            MovimientoInventario.objects.create(
                solicitud=solicitud,
                material=item.material,
                tipo='SALIDA',
                cantidad=item.cantidad_solicitada or item.cantidad,
                cantidad_solicitada=item.cantidad_solicitada or item.cantidad,
                ubicacion_origen=solicitud.ubicacion_origen,
                orden_trabajo=solicitud.orden_trabajo,
                usuario=request.user,
            )

    # Determinar estado: requiere autorización si existe al menos un aprobador
    # (aprobadores por departamento de los materiales o, como respaldo, el jefe
    # del solicitante). Si no hay ninguno, pasa directo a despacho.
    try:
        from .utils_n8n import _obtener_aprobadores_solicitud
        perfil_sol = getattr(request.user, 'perfil', None)
        jefe = getattr(perfil_sol, 'responsable', None) if perfil_sol else None
        aprobadores = _obtener_aprobadores_solicitud(solicitud, jefe)
    except Exception:
        aprobadores = []
    solicitud.estado = 'PENDIENTE_AUTORIZACION' if aprobadores else 'PENDIENTE'
    solicitud.save(update_fields=['estado'])

    # Notificaciones
    if solicitud.estado == 'PENDIENTE_AUTORIZACION':
        try:
            from .utils_ntfy import notificar_pendiente_aprobacion
            notificar_pendiente_aprobacion(solicitud)
        except Exception:
            pass
    else:
        try:
            from .utils_ntfy import notificar_nueva_solicitud
            notificar_nueva_solicitud(solicitud)
        except Exception:
            pass
    
    try:
        from .utils_n8n import notify_powerautomate_solicitud
        notify_powerautomate_solicitud(solicitud)
    except Exception:
        pass
    
    return JsonResponse({'status': 'success', 'message': f'Solicitud #{solicitud.id} enviada correctamente.'})


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
    discrepancias = MovimientoInventario.objects.filter(es_inconsistente=True, estado='APROBADO').select_related('material', 'material__unidad_medida', 'ubicacion_origen', 'usuario').order_by('-fecha_movimiento')
    discrepancias_count = discrepancias.count()

    # Confiscaciones en Tránsito
    from seguridad.models import LevantamientoConfiscacion
    confiscaciones_transito_count = LevantamientoConfiscacion.objects.filter(objetos__status='TRANSITO').distinct().count()
    
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
        'confiscaciones_transito': confiscaciones_transito_count,
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
    
    # Si viene ?solicitud=ID, abrir automáticamente esa solicitud
    solicitud_directa = request.GET.get('solicitud', '')
    
    context = {
        'pedidos_pendientes': pedidos_pendientes,
        'solicitud_directa': solicitud_directa,
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
@mobile_permission_required('logistica')
def mobile_devolucion_view(request):
    """
    Vista móvil para que el almacenista registre una devolución de materiales.
    """
    from activos.models import Ubicacion
    from .models import CategoriaMaterial
    from django.db.models import Q

    # Ubicaciones tipo Bodega o Almacén para recibir la devolución
    ubicaciones = Ubicacion.objects.filter(
        Q(tipo='ALMACEN') | Q(tipo='BODEGA') | Q(es_almacen=True)
    ).order_by('nombre')
    
    context = {
        'ubicaciones': ubicaciones,
        'categorias': CategoriaMaterial.objects.all().order_by('nombre'),
        'title': 'Devolución de Materiales'
    }
    return render(request, 'inventarios/mobile_devolucion.html', context)

@login_required
@mobile_permission_required('logistica')
def mobile_historial_devoluciones_view(request):
    """
    Vista móvil para ver el historial de devoluciones de materiales.
    """
    from .models import DevolucionMaterial
    
    # Obtener las últimas 50 devoluciones, optimizando con select_related
    devoluciones = DevolucionMaterial.objects.select_related(
        'usuario_recibe', 'persona_devuelve', 'ubicacion_destino'
    ).prefetch_related('items').order_by('-fecha_devolucion')[:50]
    
    context = {
        'devoluciones': devoluciones,
        'title': 'Historial de Devoluciones'
    }
    return render(request, 'inventarios/mobile_historial_devoluciones.html', context)

@csrf_exempt
@login_required
def api_registrar_devolucion(request):
    """
    API para registrar una devolución de materiales desde la App móvil.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    try:
        # La data viene como FormData para soportar las fotos
        persona_devuelve_id = request.POST.get('persona_devuelve_id')
        ubicacion_id = request.POST.get('ubicacion_id')
        comentarios = request.POST.get('comentarios', '')
        items_json = request.POST.get('items') # JSON stringified list
        
        if not persona_devuelve_id or not ubicacion_id or not items_json:
            return JsonResponse({'status': 'error', 'message': 'Faltan campos obligatorios'}, status=400)

        items = json.loads(items_json)
        if not items:
            return JsonResponse({'status': 'error', 'message': 'No hay materiales en la devolución'}, status=400)

        from django.contrib.auth.models import User
        persona_devuelve = get_object_or_404(User, id=persona_devuelve_id)
        ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
        
        with transaction.atomic():
            from .models import DevolucionMaterial, ItemDevolucion, FotoDevolucion, Material, MovimientoInventario
            
            # 1. Crear Cabecera
            devolucion = DevolucionMaterial.objects.create(
                usuario_recibe=request.user,
                persona_devuelve=persona_devuelve,
                ubicacion_destino=ubicacion,
                comentarios=comentarios
            )
            
            # 2. Procesar Materiales
            for item in items:
                material_id = item.get('material_id')
                cantidad = Decimal(str(item.get('cantidad', 0)))
                estado_fisico = item.get('estado', 'NUEVO') # 'NUEVO' o 'USADO'
                
                if cantidad <= 0: continue
                
                material_original = get_object_or_404(Material, id=material_id)
                material_a_recibir = material_original
                
                # Lógica para USADO
                if estado_fisico == 'USADO':
                    if material_original.sku.endswith('-USADO'):
                        # Si ya es un material marcado como usado, lo recibimos directamente
                        material_a_recibir = material_original
                    else:
                        sku_usado = f"{material_original.sku}-USADO"
                        material_usado = Material.objects.filter(sku=sku_usado).first()
                        
                        if not material_usado:
                            # Crear nuevo material para el stock usado si no existe
                            material_usado = Material.objects.create(
                                nombre=f"{material_original.nombre} (USADO)",
                                sku=sku_usado,
                                marca=material_original.marca,
                                descripcion=f"Material recuperado/usado de: {material_original.nombre}. {material_original.descripcion or ''}",
                                categoria=material_original.categoria,
                                unidad_medida=material_original.unidad_medida,
                                precio_estimado=material_original.precio_estimado * Decimal('0.5'), # 50% valor estimado por ser usado
                                tipo_material=material_original.tipo_material,
                                imagen=material_original.imagen
                            )
                        material_a_recibir = material_usado
                
                # 3. Crear Item de Devolución
                ItemDevolucion.objects.create(
                    devolucion=devolucion,
                    material_original=material_original,
                    material_recibido=material_a_recibir,
                    cantidad=cantidad,
                    estado_fisico=estado_fisico
                )
                
                # 4. Crear Movimiento de Inventario (Entrada)
                # Se crea como APROBADO de una vez porque el almacenista lo está recibiendo físicamente
                mov = MovimientoInventario.objects.create(
                    material=material_a_recibir,
                    tipo='ENTRADA',
                    cantidad=cantidad,
                    ubicacion_destino=ubicacion,
                    usuario=request.user,
                    devolucion=devolucion,
                    comentarios=f"Devolución #{devolucion.id} por {persona_devuelve.get_full_name() or persona_devuelve.username}. Estado: {estado_fisico}",
                    estado='APROBADO',
                    aprobado_por=request.user,
                    fecha_aprobacion=timezone.now()
                )
            
            # 5. Procesar Fotos
            photos = request.FILES.getlist('fotos')
            for p in photos:
                FotoDevolucion.objects.create(
                    devolucion=devolucion,
                    imagen=p
                )
                
        return JsonResponse({
            'status': 'success', 
            'message': f'Devolución #{devolucion.id} registrada correctamente.',
            'devolucion_id': devolucion.id
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def api_search_usuarios(request):
    """
    API para buscar usuarios (personal registrado) por nombre o username.
    """
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'results': []})
    
    from django.contrib.auth.models import User
    from django.db.models import Q
    
    usuarios = User.objects.filter(
        Q(first_name__icontains=q) | 
        Q(last_name__icontains=q) | 
        Q(username__icontains=q)
    ).distinct()[:10]
    
    results = []
    for u in usuarios:
        results.append({
            'id': u.id,
            'nombre_completo': u.get_full_name() or u.username,
            'username': u.username
        })
        
    return JsonResponse({'results': results})

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
        'active_tab': 'catalogo',
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

                    if material.no_afecta_stock:
                        continue

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

            marca_id = request.POST.get('marca_id')
            marca_nombre = request.POST.get('marca_nombre', '').strip()
            tipo_material = request.POST.get('tipo_material', 'INSUMO')
            descripcion = request.POST.get('descripcion', '')
            no_afecta_stock = request.POST.get('no_afecta_stock') == 'true'

            if not nombre or not sku:
                return JsonResponse({'status': 'error', 'message': 'Nombre y SKU son obligatorios'}, status=400)

            # Limpiar IDs de FKs (evitar strings vacíos)
            categoria_id = int(categoria_id) if categoria_id and str(categoria_id).isdigit() else None
            unidad_id = int(unidad_id) if unidad_id and str(unidad_id).isdigit() else None
            ubicacion_id = int(ubicacion_id) if ubicacion_id and str(ubicacion_id).isdigit() else None
            marca_id = int(marca_id) if marca_id and str(marca_id).isdigit() else None

            # Si no hay marca_id pero sí marca_nombre, crear o buscar la marca
            if not marca_id and marca_nombre:
                from activos.models import Marca
                marca_obj, _ = Marca.objects.get_or_create(nombre__iexact=marca_nombre, defaults={'nombre': marca_nombre})
                marca_id = marca_obj.id

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
                    if marca_id: existing_material.marca_id = marca_id
                    if descripcion: existing_material.descripcion = descripcion
                    existing_material.tipo_material = tipo_material if tipo_material in dict(Material.TIPO_MATERIAL_CHOICES) else 'INSUMO'
                    existing_material.no_afecta_stock = no_afecta_stock
                    existing_material.save()
                    material = existing_material
                    created = False
                else:
                    # Crear nuevo
                    material = Material.objects.create(
                        sku=sku,
                        nombre=nombre,
                        categoria_id=categoria_id if categoria_id else None,
                        unidad_medida_id=unidad_id if unidad_id else None,
                        marca_id=marca_id,
                        tipo_material=tipo_material if tipo_material in dict(Material.TIPO_MATERIAL_CHOICES) else 'INSUMO',
                        descripcion=descripcion,
                        no_afecta_stock=no_afecta_stock,
                    )
                    created = True

                # 2. Procesar Fotos
                fotos = request.FILES.getlist('fotos')
                for i, f in enumerate(fotos):
                    FotoMaterial.objects.create(material=material, imagen=f)
                    # Si el material no tiene imagen principal, usar la primera que llegue
                    if i == 0 and not material.imagen:
                        material.imagen = f
                        material.save()

                # 3. Stock Inicial (solo para materiales que afectan stock)
                if stock_inicial > 0 and ubicacion_id and not no_afecta_stock:
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
const CACHE_NAME = 'inventarios-pwa-v3';
const urlsToCache = [
  '/inventarios/mobile/dashboard/',
  '/inventarios/mobile/catalog/',
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
        .then(response => {
          if (!response.ok && response.status >= 500) {
            return caches.match(event.request).then(cachedRes => {
              return cachedRes || response;
            });
          }
          return response;
        })
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


@login_required
def api_liquidar_movimiento(request, mov_id):
    """
    Aprueba (liquida) o rechaza un movimiento pendiente individual.
    POST body: { "accion": "aprobar" | "rechazar", "comentario": "..." }
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    # Solo usuarios del grupo Almacenes o superusuarios
    es_almacen = request.user.groups.filter(name='Almacenes').exists() or request.user.is_superuser
    if not es_almacen:
        return JsonResponse({'status': 'error', 'message': 'No tienes permiso para aprobar movimientos.'}, status=403)

    mov = get_object_or_404(MovimientoInventario, pk=mov_id)

    if mov.estado != 'PENDIENTE':
        return JsonResponse({'status': 'error', 'message': f'El movimiento ya fue procesado ({mov.get_estado_display()}).'}, status=400)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}

    accion = data.get('accion', 'aprobar')
    comentario = data.get('comentario', '')

    if accion == 'rechazar':
        mov.estado = 'RECHAZADO'
        if comentario:
            mov.comentarios = (mov.comentarios or '') + f' | Rechazado: {comentario}'
        mov.save()
        return JsonResponse({'status': 'success', 'message': 'Movimiento rechazado.'})

    # Aprobar / Liquidar
    try:
        if comentario:
            mov.comentarios = (mov.comentarios or '') + f' | {comentario}'
            mov.save()
        mov.liquidar(request.user)
        return JsonResponse({
            'status': 'success',
            'message': f'Movimiento #{mov.id} aprobado. Stock actualizado.',
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def api_detalle_movimiento(request, mov_id):
    """
    Retorna todos los detalles de un movimiento de inventario para mostrar en modal.
    """
    mov = get_object_or_404(
        MovimientoInventario.objects.select_related(
            'material', 'material__categoria', 'material__unidad_medida',
            'lote', 'solicitud', 'solicitud__usuario', 'solicitud__orden_trabajo',
            'ingreso', 'devolucion', 'orden_trabajo',
            'ubicacion_origen', 'ubicacion_destino',
            'usuario', 'aprobado_por'
        ),
        pk=mov_id
    )

    data = {
        'id': mov.id,
        'material': {
            'id': mov.material.id,
            'nombre': mov.material.nombre,
            'sku': mov.material.sku,
            'categoria': mov.material.categoria.nombre if mov.material.categoria else 'General',
            'unidad': mov.material.unidad_medida.nombre if mov.material.unidad_medida else 'Unidad',
            'imagen': mov.material.imagen.url if mov.material.imagen else None,
        },
        'tipo': mov.get_tipo_display(),
        'tipo_raw': mov.tipo,
        'cantidad': float(mov.cantidad),
        'cantidad_solicitada': float(mov.cantidad_solicitada) if mov.cantidad_solicitada else None,
        'estado': mov.get_estado_display(),
        'estado_raw': mov.estado,
        'fecha': mov.fecha_movimiento.strftime('%d/%m/%Y %H:%M'),
        'ubicacion_origen': mov.ubicacion_origen.nombre if mov.ubicacion_origen else None,
        'ubicacion_destino': mov.ubicacion_destino.nombre if mov.ubicacion_destino else None,
        'ubicacion_especifica': mov.ubicacion_especifica or None,
        'lote': str(mov.lote) if mov.lote else None,
        'comentarios': mov.comentarios or '',
        'es_inconsistente': mov.es_inconsistente,
        'usuario': mov.usuario.get_full_name() or mov.usuario.username if mov.usuario else 'Sistema',
        'aprobado_por': mov.aprobado_por.get_full_name() if mov.aprobado_por else None,
        'fecha_aprobacion': mov.fecha_aprobacion.strftime('%d/%m/%Y %H:%M') if mov.fecha_aprobacion else None,
        'solicitud': {
            'id': mov.solicitud.id,
            'usuario': mov.solicitud.usuario.get_full_name() or mov.solicitud.usuario.username,
            'estado': mov.solicitud.get_estado_display(),
            'fecha': mov.solicitud.fecha_solicitud.strftime('%d/%m/%Y %H:%M'),
        } if mov.solicitud else None,
        'orden_trabajo': {
            'id': mov.orden_trabajo.id,
            'codigo': mov.orden_trabajo.codigo_de_orden,
            'tipo': mov.orden_trabajo.get_tipo_display(),
            'descripcion': mov.orden_trabajo.descripcion_corta or '',
        } if mov.orden_trabajo else None,
        'ingreso': {
            'id': mov.ingreso.id,
            'fecha': mov.ingreso.fecha_ingreso.strftime('%d/%m/%Y %H:%M'),
            'usuario': mov.ingreso.usuario.get_full_name() if mov.ingreso.usuario else '',
        } if mov.ingreso else None,
    }

    return JsonResponse({'status': 'success', 'movimiento': data})


@login_required
def api_vincular_ot_movimiento(request, mov_id):
    """
    POST: Vincula o desvincula una OT de un movimiento.
    Body: { "orden_trabajo_id": <int|null> }
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    mov = get_object_or_404(MovimientoInventario, pk=mov_id)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)

    ot_id = data.get('orden_trabajo_id')

    if ot_id:
        ot = get_object_or_404(OrdenTrabajo, pk=ot_id)
        mov.orden_trabajo = ot
        mov.save(update_fields=['orden_trabajo'])
        return JsonResponse({
            'status': 'success',
            'message': f'Movimiento vinculado a {ot.codigo_de_orden}',
            'orden_trabajo': {
                'id': ot.id,
                'codigo': ot.codigo_de_orden,
                'tipo': ot.get_tipo_display(),
                'descripcion': ot.descripcion_corta or '',
            }
        })
    else:
        mov.orden_trabajo = None
        mov.save(update_fields=['orden_trabajo'])
        return JsonResponse({'status': 'success', 'message': 'OT desvinculada del movimiento.'})


@csrf_exempt
def api_autorizar_solicitud(request, pk):
    """
    Endpoint (Webhook) para que n8n confirme la autorización
    de una solicitud de materiales por parte del jefe inmediato.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    solicitud = get_object_or_404(SolicitudMaterial, pk=pk)
    
    if solicitud.estado != 'PENDIENTE_AUTORIZACION':
        return JsonResponse({'status': 'error', 'message': f'La solicitud ya no está pendiente de autorización. Estado actual: {solicitud.estado}'}, status=400)
    
    try:
        data = json.loads(request.body)
    except:
        data = request.POST

    accion = data.get('accion', '').lower()
    
    if accion == 'aprobar':
        solicitud.estado = 'PENDIENTE'
        solicitud.save()
        
        # Push notification vía ntfy al almacén
        from .utils_ntfy import notificar_nueva_solicitud
        notificar_nueva_solicitud(solicitud)
        
        return JsonResponse({'status': 'success', 'message': f'Solicitud #{solicitud.id} aprobada. Almacén notificado.'})
        
    elif accion == 'rechazar':
        solicitud.estado = 'RECHAZADO'
        solicitud.save()
        # Rechazar todos los movimientos asociados
        solicitud.items.update(estado='RECHAZADO')
        
        return JsonResponse({'status': 'success', 'message': f'Solicitud #{solicitud.id} rechazada.'})
        
    else:
        return JsonResponse({'status': 'error', 'message': 'Acción inválida. Use "aprobar" o "rechazar".'}, status=400)

@csrf_exempt
@login_required
def api_sync_offline_queue(request):
    if request.method != 'POST': return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    import json
    from decimal import Decimal
    from collections import defaultdict
    try:
        data = json.loads(request.body)
        queue = data.get('queue', [])
        if not queue: return JsonResponse({'status': 'success', 'message': 'Cola vacía'})
        errores = []
        from django.db import transaction
        from .models import Material, MovimientoInventario, StockRecord
        from activos.models import Ubicacion

        # Agrupar por material + ubicacion + tipo
        groups = defaultdict(lambda: defaultdict(Decimal))
        for mov_data in queue:
            try:
                material_id = mov_data.get('material_id')
                tipo = mov_data.get('tipo', 'ENTRADA').upper()
                cantidad = Decimal(str(mov_data.get('cantidad', 0)))
                ubicacion_id = mov_data.get('ubicacion_id')
                if not material_id or not ubicacion_id or cantidad <= 0:
                    raise ValueError('Datos inválidos')
                groups[(material_id, ubicacion_id)][tipo] += cantidad
            except Exception as e:
                errores.append({'item': mov_data, 'error': str(e)})

        procesados = 0
        with transaction.atomic():
            for (material_id, ubicacion_id), tipos in groups.items():
                try:
                    material = Material.objects.get(id=material_id)
                    ubicacion = Ubicacion.objects.get(id=ubicacion_id)
                    neto = tipos.get('ENTRADA', Decimal('0')) - tipos.get('SALIDA', Decimal('0'))
                    if 'AJUSTE' in tipos:
                        stock_record = StockRecord.objects.filter(material=material, ubicacion=ubicacion).first()
                        stock_actual = stock_record.cantidad if stock_record else Decimal('0')
                        ajuste_destino = tipos['AJUSTE']
                        delta = ajuste_destino - stock_actual
                        neto += delta
                    if neto == 0:
                        continue
                    final_tipo = 'ENTRADA' if neto > 0 else 'SALIDA'
                    final_qty = abs(neto)
                    comentarios = f'Sincronizado offline (agrupado)'
                    movimiento = MovimientoInventario(
                        material=material, tipo=final_tipo, cantidad=final_qty,
                        usuario=request.user, comentarios=comentarios
                    )
                    if final_tipo == 'ENTRADA':
                        movimiento.ubicacion_destino = ubicacion
                    else:
                        movimiento.ubicacion_origen = ubicacion
                    movimiento.save()
                    movimiento.liquidar(request.user)
                    procesados += 1
                except Exception as e:
                    errores.append({'item': f'material {material_id}', 'error': str(e)})
        return JsonResponse({'status': 'success', 'message': f'{procesados} movimiento(s) creado(s) agrupado(s)', 'errores': errores})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def api_recalcular_stock(request, material_id):
    from .models import Material
    try:
        mat = get_object_or_404(Material, id=material_id)
        mat.recalcular_stock()
        total = mat.existencias.aggregate(s=Sum('cantidad'))['s'] or 0
        return JsonResponse({'status': 'success', 'stock_total': float(total)})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def api_check_ot_solicitud(request, ot_id):
    """
    Verifica si una Orden de Trabajo ya tiene una solicitud de materiales
    pendiente (no finalizada). Si existe, retorna sus datos para preguntar
    al usuario si quiere continuar con esa solicitud anterior.
    """
    solicitud = SolicitudMaterial.objects.filter(
        orden_trabajo_id=ot_id
    ).exclude(
        estado__in=['ENTREGADO', 'RECHAZADO']
    ).order_by('-fecha_solicitud').first()

    if solicitud:
        items_count = solicitud.items.count()
        return JsonResponse({
            'has_pending': True,
            'solicitud': {
                'id': solicitud.id,
                'estado': solicitud.estado,
                'fecha': solicitud.fecha_solicitud.strftime('%d/%m/%Y %H:%M'),
                'items_count': items_count,
            }
        })
    return JsonResponse({'has_pending': False})


@login_required
def api_aprobadores_solicitud(request, pk):
    """
    Devuelve la lista de personas autorizadas para aprobar una solicitud.

    Usa la misma lógica que el webhook de autorización
    (_obtener_aprobadores_solicitud): aprobadores de salida de los departamentos
    de los materiales y, como fallback, el superior/jefe del solicitante.

    Respuesta JSON con la lista de aprobadores. Si se abre en el navegador con
    ?format=html, muestra una tabla legible.
    """
    from .utils_n8n import _obtener_aprobadores_solicitud

    solicitud = get_object_or_404(SolicitudMaterial, pk=pk)

    # Determinar el superior del solicitante (fallback) igual que en el webhook
    user = solicitud.usuario
    perfil = getattr(user, 'perfil', None)
    jefe_directo = getattr(perfil, 'responsable', None) if perfil else None
    jefe_departamento = None
    if perfil and getattr(perfil, 'departamento', None):
        jefe_departamento = getattr(perfil.departamento, 'responsable', None)
    superior = jefe_directo or jefe_departamento

    aprobadores = _obtener_aprobadores_solicitud(solicitud, superior)

    if request.GET.get('format') == 'html':
        filas = ''.join(
            f"<tr><td>{a.get('nombre','')}</td><td>{a.get('email','') or '—'}</td>"
            f"<td>{a.get('departamento','') or '—'}</td></tr>"
            for a in aprobadores
        ) or '<tr><td colspan="3" style="text-align:center;color:#6a6d70;">Sin aprobadores configurados</td></tr>'
        html = f"""
        <div style="font-family:'Outfit',sans-serif;max-width:640px;margin:24px auto;">
          <h2 style="color:#32363a;">Personas autorizadas para aprobar la Solicitud #{solicitud.id}</h2>
          <p style="color:#6a6d70;">Estado actual: <strong>{solicitud.get_estado_display()}</strong> ·
             Solicitante: {(f"{user.first_name} {user.last_name}".strip() or user.username)}</p>
          <table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
            <thead><tr style="background:#f0f4f8;">
              <th style="border:1px solid #d9d9d9;padding:8px;text-align:left;">Nombre</th>
              <th style="border:1px solid #d9d9d9;padding:8px;text-align:left;">Correo</th>
              <th style="border:1px solid #d9d9d9;padding:8px;text-align:left;">Departamento</th>
            </tr></thead>
            <tbody>{filas}</tbody>
          </table>
        </div>
        """
        return HttpResponse(html)

    return JsonResponse({
        'status': 'success',
        'solicitud_id': solicitud.id,
        'estado': solicitud.estado,
        'estado_display': solicitud.get_estado_display(),
        'total': len(aprobadores),
        'aprobadores': aprobadores,
    })


@login_required
def api_solicitud_update_items(request, pk):
    """
    Actualiza items de una solicitud: agrega nuevos, modifica cantidades y elimina líneas.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    solicitud = get_object_or_404(SolicitudMaterial, pk=pk)

    # Puede editar: el dueño de la solicitud o el personal de Almacenes (almacenista)
    es_dueno = solicitud.usuario_id == request.user.id
    es_almacen = request.user.groups.filter(name__iexact='Almacenes').exists() or request.user.is_superuser
    if not (es_dueno or es_almacen):
        return JsonResponse({'status': 'error', 'message': 'No tienes permiso para modificar esta solicitud.'}, status=403)

    if solicitud.estado in ('ENTREGADO', 'RECHAZADO'):
        return JsonResponse({'status': 'error', 'message': 'La solicitud ya está finalizada'}, status=400)

    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)

    items = data.get('items', [])
    resultados = {'creados': 0, 'actualizados': 0, 'eliminados': 0}

    for it in items:
        mov_id = it.get('mov_id')
        material_id = it.get('material_id')
        cantidad = it.get('cantidad')
        eliminar = it.get('_delete', False)

        if eliminar and mov_id:
            try:
                mov = MovimientoInventario.objects.get(id=mov_id, solicitud=solicitud, estado='PENDIENTE')
                mov.delete()
                resultados['eliminados'] += 1
            except MovimientoInventario.DoesNotExist:
                continue

        elif mov_id and cantidad is not None:
            try:
                mov = MovimientoInventario.objects.get(id=mov_id, solicitud=solicitud, estado='PENDIENTE')
                dc = Decimal(str(cantidad))
                if dc <= 0:
                    mov.delete()
                    resultados['eliminados'] += 1
                else:
                    mov.cantidad = dc
                    mov.cantidad_solicitada = dc
                    mov.save()
                    resultados['actualizados'] += 1
            except MovimientoInventario.DoesNotExist:
                continue

        elif material_id and cantidad is not None:
            try:
                material = Material.objects.get(id=material_id)
                dc = Decimal(str(cantidad))
                if dc <= 0:
                    continue
                MovimientoInventario.objects.create(
                    solicitud=solicitud,
                    material=material,
                    tipo='SALIDA',
                    cantidad=dc,
                    cantidad_solicitada=dc,
                    ubicacion_origen=solicitud.ubicacion_origen,
                    orden_trabajo=solicitud.orden_trabajo,
                    usuario=request.user,
                    comentarios=solicitud.comentarios_solicitud or ''
                )
                resultados['creados'] += 1
            except Material.DoesNotExist:
                continue

    return JsonResponse({
        'status': 'success',
        'message': f"{resultados['creados']} creado(s), {resultados['actualizados']} actualizado(s), {resultados['eliminados']} eliminado(s)",
        **resultados
    })


@login_required
def api_resolicitud_webhook(request, pk):
    """Reenvía el webhook a Power Automate para una solicitud."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    solicitud = get_object_or_404(SolicitudMaterial, pk=pk)

    # Puede reenviar: el dueño, cualquier persona del mismo departamento del
    # solicitante, un aprobador de salidas, el personal de Almacenes o un superusuario.
    perfil = getattr(request.user, 'perfil', None)
    mi_departamento_id = getattr(getattr(perfil, 'departamento', None), 'id', None)
    sol_perfil = getattr(solicitud.usuario, 'perfil', None)
    sol_departamento_id = getattr(getattr(sol_perfil, 'departamento', None), 'id', None)

    es_dueno = solicitud.usuario_id == request.user.id
    mismo_departamento = bool(mi_departamento_id and mi_departamento_id == sol_departamento_id)
    es_aprobador = bool(perfil and getattr(perfil, 'aprobador_salidas', False))
    es_almacen = request.user.groups.filter(name__iexact='Almacenes').exists()
    if not (es_dueno or mismo_departamento or es_aprobador or es_almacen or request.user.is_superuser):
        return JsonResponse({'status': 'error', 'message': 'No tienes permiso para reenviar esta solicitud.'}, status=403)

    from .utils_n8n import notify_powerautomate_solicitud
    ok = notify_powerautomate_solicitud(solicitud)
    if ok:
        return JsonResponse({'status': 'success', 'message': 'Webhook reenviado correctamente'})
    return JsonResponse({'status': 'error', 'message': 'Error al enviar webhook'}, status=500)


# ═══════════════════════════════════════════════════════════════════════════════
# MODIFICACIÓN DE INVENTARIO (Conteo Físico)
# Solo accesible por grupo "Almacenes"
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def mobile_modificacion_inventario(request):
    """Vista para realizar conteo físico / ajuste de inventario."""
    # Verificar pertenencia al grupo Almacenes
    if not request.user.groups.filter(name='Almacenes').exists() and not request.user.is_superuser:
        messages.error(request, 'No tienes permiso para acceder a esta sección.')
        return redirect('inventarios:mobile_dashboard')
    
    from .models import Material, StockRecord
    from activos.models import Ubicacion
    from django.db.models import Q, Sum
    
    # Obtener ubicaciones de almacén
    ubicaciones = Ubicacion.objects.filter(
        Q(tipo='ALMACEN') | Q(tipo='BODEGA') | Q(es_almacen=True)
    ).order_by('nombre')
    
    # Ubicación seleccionada (default: primera)
    ubicacion_id = request.GET.get('ubicacion')
    ubicacion_actual = None
    materiales_data = []
    
    if ubicacion_id:
        ubicacion_actual = get_object_or_404(Ubicacion, pk=ubicacion_id)
        # Obtener materiales con stock en esta ubicación
        stock_records = StockRecord.objects.filter(
            ubicacion=ubicacion_actual
        ).select_related('material', 'material__categoria', 'material__unidad_medida').order_by('material__nombre')
        
        for sr in stock_records:
            materiales_data.append({
                'id': sr.material.id,
                'sku': sr.material.sku,
                'nombre': sr.material.nombre,
                'categoria': sr.material.categoria.nombre if sr.material.categoria else 'General',
                'unidad': sr.material.unidad_medida.abreviatura if sr.material.unidad_medida else 'und',
                'stock_sistema': float(sr.cantidad),
            })
    
    context = {
        'ubicaciones': ubicaciones,
        'ubicacion_actual': ubicacion_actual,
        'materiales_json': json.dumps(materiales_data),
    }
    return render(request, 'inventarios/mobile_modificacion_inventario.html', context)


@csrf_exempt
@login_required
def api_guardar_conteo_inventario(request):
    """Guarda los ajustes de inventario como movimientos."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    # Verificar permiso
    if not request.user.groups.filter(name='Almacenes').exists() and not request.user.is_superuser:
        return JsonResponse({'error': 'Sin permiso'}, status=403)
    
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    ubicacion_id = data.get('ubicacion_id')
    items = data.get('items', [])
    comentario_general = data.get('comentario', 'Conteo físico de inventario')
    
    if not ubicacion_id or not items:
        return JsonResponse({'error': 'Faltan datos requeridos'}, status=400)
    
    ubicacion = get_object_or_404(Ubicacion, pk=ubicacion_id)
    movimientos_creados = 0
    
    with transaction.atomic():
        for item in items:
            material_id = item.get('material_id')
            cantidad_real = Decimal(str(item.get('cantidad_real', 0)))
            stock_sistema = Decimal(str(item.get('stock_sistema', 0)))
            
            diferencia = cantidad_real - stock_sistema
            if diferencia == 0:
                continue  # Sin cambio, no registrar
            
            material = Material.objects.get(pk=material_id)
            
            # Crear movimiento de ajuste
            mov = MovimientoInventario.objects.create(
                material=material,
                tipo='AJUSTE',
                cantidad=abs(diferencia),
                ubicacion_origen=ubicacion if diferencia < 0 else None,
                ubicacion_destino=ubicacion if diferencia > 0 else None,
                usuario=request.user,
                comentarios=f"{comentario_general} | Sistema: {stock_sistema}, Real: {cantidad_real}, Dif: {diferencia:+}",
                estado='APROBADO',
                aprobado_por=request.user,
                fecha_aprobacion=timezone.now(),
            )
            
            # Actualizar StockRecord directamente
            sr, _ = StockRecord.objects.get_or_create(
                material=material,
                ubicacion=ubicacion,
                lote=None,
                ubicacion_especifica='',
                defaults={'cantidad': 0}
            )
            sr.cantidad = cantidad_real
            sr.save()
            
            movimientos_creados += 1
    
    return JsonResponse({
        'status': 'success',
        'message': f'{movimientos_creados} ajuste(s) registrado(s) correctamente.',
        'movimientos': movimientos_creados,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# FORMULARIO DE APROBACIÓN (accesible vía link de ntfy)
# ═══════════════════════════════════════════════════════════════════════════════

def formulario_aprobacion_solicitud(request, pk, token):
    """Formulario web para aprobar/rechazar solicitud. Requiere login y ser el jefe del solicitante."""
    import hashlib
    
    # Requiere login — redirige al login si no está autenticado
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    
    solicitud = get_object_or_404(SolicitudMaterial.objects.select_related(
        'usuario', 'usuario__perfil', 'orden_trabajo', 'ubicacion_origen', 'edificio_destino', 'nivel_destino'
    ), pk=pk)
    
    # Verificar token
    expected_token = hashlib.sha256(f"{solicitud.id}-{solicitud.fecha_solicitud}".encode()).hexdigest()[:16]
    if token != expected_token:
        return render(request, 'inventarios/aprobacion_solicitud.html', {'error': 'Token inválido o expirado.'})
    
    # Verificar que el usuario logueado sea el jefe del solicitante o superusuario
    jefe_esperado = getattr(solicitud.usuario, 'perfil', None) and getattr(solicitud.usuario.perfil, 'responsable', None)
    es_autorizado = (
        request.user.is_superuser or 
        request.user == jefe_esperado or
        (hasattr(request.user, 'perfil') and request.user.perfil.departamento and 
         request.user.perfil.departamento.aprobador == request.user)
    )
    
    if not es_autorizado:
        return render(request, 'inventarios/aprobacion_solicitud.html', {
            'error': f'No tienes permiso para aprobar esta solicitud. Solo el jefe del solicitante ({jefe_esperado or "no asignado"}) puede hacerlo.'
        })
    
    ya_procesada = solicitud.estado != 'PENDIENTE_AUTORIZACION'
    
    if request.method == 'POST' and not ya_procesada:
        accion = request.POST.get('accion')
        comentario = request.POST.get('comentario', '')
        
        if accion == 'aprobar':
            solicitud.estado = 'PENDIENTE'
            solicitud.comentarios_almacen = (solicitud.comentarios_almacen or '') + f"\n[Aprobado por {request.user.get_full_name() or request.user.username}] {comentario}".strip()
            solicitud.save()
            
            # Notificar al almacén vía ntfy
            from .utils_ntfy import notificar_nueva_solicitud
            notificar_nueva_solicitud(solicitud)
            
            return render(request, 'inventarios/aprobacion_solicitud.html', {
                'solicitud': solicitud,
                'resultado': 'aprobada',
            })
        
        elif accion == 'rechazar':
            solicitud.estado = 'RECHAZADO'
            solicitud.comentarios_almacen = (solicitud.comentarios_almacen or '') + f"\n[Rechazado por {request.user.get_full_name() or request.user.username}] {comentario}".strip()
            solicitud.save()
            solicitud.items.update(estado='RECHAZADO')
            
            return render(request, 'inventarios/aprobacion_solicitud.html', {
                'solicitud': solicitud,
                'resultado': 'rechazada',
            })
    
    # GET: mostrar formulario
    items = solicitud.items.select_related('material').all()
    
    return render(request, 'inventarios/aprobacion_solicitud.html', {
        'solicitud': solicitud,
        'items': items,
        'ya_procesada': ya_procesada,
        'token': token,
    })


from .models import Rack, RackPosition
from django.db.models import Sum
import json

@staff_member_required
def rack_list_view(request):
    racks = Rack.objects.filter(activo=True).select_related('bodega').order_by('bodega__nombre', 'orden')
    total_posiciones = sum(r.total_posiciones for r in racks)
    bodegas_con_racks = racks.values_list('bodega', flat=True).distinct().count()
    from activos.models import Ubicacion
    from django.db.models import Q
    ubicaciones = Ubicacion.objects.filter(Q(tipo='BODEGA') | Q(es_almacen=True)).order_by('nombre')
    return render(request, 'inventarios/racks_list.html', {
        'racks': racks,
        'total_racks': racks.count(),
        'total_posiciones': total_posiciones,
        'bodegas_con_racks': bodegas_con_racks,
        'ubicaciones': ubicaciones,
        'active_tab': 'racks',
        'title': 'Racks / Estanterías',
    })

@staff_member_required
def rack_3d_view(request, pk):
    rack = get_object_or_404(Rack.objects.select_related('bodega'), pk=pk)
    posiciones = rack.posiciones.select_related('material').all()
    rack_data = {
        'nombre': rack.nombre,
        'bodega': rack.bodega.nombre,
        'largo': float(rack.largo),
        'alto': float(rack.alto),
        'num_niveles': rack.num_niveles,
        'num_secciones': rack.num_secciones,
        'posiciones': [
            {
                'id': p.id,
                'nivel': p.nivel,
                'seccion': p.seccion,
                'codigo': p.codigo,
                'material_id': p.material_id,
                'material_nombre': p.material.nombre if p.material else None,
                'cantidad': float(p.cantidad),
                'peso': float(p.material.peso) if p.material and p.material.peso else None,
                'ancho': float(p.material.ancho) if p.material and p.material.ancho else None,
                'alto': float(p.material.alto) if p.material and p.material.alto else None,
                'profundidad': float(p.material.profundidad) if p.material and p.material.profundidad else None,
                'tipo_material': p.material.tipo_material if p.material else None,
            }
            for p in posiciones
        ],
    }
    return render(request, 'inventarios/rack_3d.html', {
        'rack': rack,
        'rack_data': json.dumps(rack_data),
    })


@csrf_exempt
def api_rack_assign_position(request, rack_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    rack = get_object_or_404(Rack, pk=rack_id)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    nivel = data.get('nivel')
    seccion = data.get('seccion')
    material_id = data.get('material_id')
    cantidad = data.get('cantidad', 1)
    if not nivel or not seccion:
        return JsonResponse({'error': 'nivel y seccion son requeridos'}, status=400)
    from .models import Material
    material = get_object_or_404(Material, pk=material_id)
    profundidad = data.get('profundidad')
    if profundidad is not None:
        try:
            profundidad_val = float(profundidad)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'profundidad debe ser mayor a 0'}, status=400)
        if profundidad_val <= 0:
            return JsonResponse({'error': 'profundidad debe ser mayor a 0'}, status=400)
    ancho = data.get('ancho')
    alto = data.get('alto')
    update_fields = []
    if ancho is not None and material.ancho != ancho:
        material.ancho = ancho
        update_fields.append('ancho')
    if alto is not None and material.alto != alto:
        material.alto = alto
        update_fields.append('alto')
    if profundidad is not None:
        material.profundidad = profundidad_val
        update_fields.append('profundidad')
    if update_fields:
        material.save(update_fields=update_fields)
    count = RackPosition.objects.filter(rack=rack, nivel=nivel, seccion=seccion).count()
    codigo = f"{rack.nombre}-{nivel}-{seccion}-{count + 1}"
    pos = RackPosition.objects.create(
        rack=rack, nivel=nivel, seccion=seccion,
        material=material, cantidad=cantidad, codigo=codigo,
    )
    return JsonResponse({
        'status': 'ok',
        'posicion': {
            'id': pos.id,
            'codigo': pos.codigo,
            'nivel': pos.nivel,
            'seccion': pos.seccion,
            'material_id': pos.material_id,
            'material_nombre': pos.material.nombre if pos.material else None,
            'cantidad': float(pos.cantidad),
            'peso': float(pos.material.peso) if pos.material and pos.material.peso else None,
            'ancho': float(pos.material.ancho) if pos.material and pos.material.ancho else None,
            'alto': float(pos.material.alto) if pos.material and pos.material.alto else None,
            'profundidad': float(pos.material.profundidad) if pos.material and pos.material.profundidad else None,
            'tipo_material': pos.material.tipo_material if pos.material else None,
        },
    })


@csrf_exempt
def api_rack_remove_position(request, rack_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    rack = get_object_or_404(Rack, pk=rack_id)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    pos_id = data.get('pos_id')
    if not pos_id:
        return JsonResponse({'error': 'pos_id es requerido'}, status=400)
    deleted, _ = RackPosition.objects.filter(rack=rack, pk=pos_id).delete()
    return JsonResponse({'status': 'ok', 'deleted': deleted})


def bodega_3d_view(request, pk):
    bodega = get_object_or_404(Ubicacion, pk=pk, tipo='BODEGA')
    racks = Rack.objects.filter(bodega=bodega, activo=True).order_by('orden', 'nombre')
    racks_data = []
    for r in racks:
        posiciones = r.posiciones.select_related('material').all()
        racks_data.append({
            'id': r.id,
            'nombre': r.nombre,
            'largo': float(r.largo),
            'alto': float(r.alto),
            'num_niveles': r.num_niveles,
            'num_secciones': r.num_secciones,
            'pos_x_m': float(r.pos_x_m) if r.pos_x_m else 0,
            'pos_y_m': float(r.pos_y_m) if r.pos_y_m else 0,
            'posiciones': [
                {
                    'id': p.id,
                    'nivel': p.nivel, 'seccion': p.seccion, 'codigo': p.codigo,
                    'material_nombre': p.material.nombre if p.material else None,
                    'cantidad': float(p.cantidad),
                    'peso': float(p.material.peso) if p.material and p.material.peso else None,
                    'ancho': float(p.material.ancho) if p.material and p.material.ancho else None,
                    'alto': float(p.material.alto) if p.material and p.material.alto else None,
                }
                for p in posiciones
            ],
        })
    ancho_m = float(bodega.ancho_m) if bodega.ancho_m is not None else 10
    largo_m = float(bodega.largo_m) if bodega.largo_m is not None else 10
    return render(request, 'inventarios/bodega_3d.html', {
        'bodega': bodega,
        'racks': racks,
        'bodega_data': json.dumps({'ancho_m': ancho_m, 'largo_m': largo_m, 'racks': racks_data}),
    })


@csrf_exempt
def api_bodega_racks(request, bodega_id):
    from .models import Rack
    bodega = get_object_or_404(Ubicacion, pk=bodega_id, tipo='BODEGA')
    racks = Rack.objects.filter(bodega=bodega, activo=True).order_by('orden', 'nombre')
    data = [{'id': r.id, 'nombre': r.nombre, 'pos_x_m': float(r.pos_x_m or 0), 'pos_y_m': float(r.pos_y_m or 0),
             'largo': float(r.largo), 'alto': float(r.alto), 'num_niveles': r.num_niveles, 'num_secciones': r.num_secciones}
            for r in racks]
    return JsonResponse({'status': 'ok', 'racks': data, 'ancho_m': float(bodega.ancho_m or 10), 'largo_m': float(bodega.largo_m or 10)})


@csrf_exempt
def api_rack_update_position(request, rack_id):
    from .models import Rack
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    rack = get_object_or_404(Rack, pk=rack_id)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    pos_x = data.get('pos_x_m')
    pos_y = data.get('pos_y_m')
    if pos_x is not None:
        rack.pos_x_m = pos_x
    if pos_y is not None:
        rack.pos_y_m = pos_y
    rack.save(update_fields=['pos_x_m', 'pos_y_m'])
    return JsonResponse({'status': 'ok', 'pos_x_m': float(rack.pos_x_m or 0), 'pos_y_m': float(rack.pos_y_m or 0)})

@login_required
def solicitud_nuevos_materiales(request):
    from presupuestos.models import ArticuloRequisicion, Requisicion
    from django.db.models import Q, Count
    from .models import CategoriaMaterial, UnidadMedida
    from activos.models import Ubicacion, Marca

    # Artículos de requisición sin material vinculado (nuevos)
    import json
    sin_material_qs = ArticuloRequisicion.objects.filter(
        material__isnull=True
    ).select_related(
        'requisicion',
        'requisicion__usuario_solicitante',
        'proveedor'
    ).order_by('-requisicion__fecha')

    sin_material = []
    for art in sin_material_qs:
        art.js_data = json.dumps({
            'id': str(art.cr8ca_itemderequisicionid),
            'articulo': art.cr8ca_articulo,
            'requisicion_id': str(art.requisicion.cr8ca_requisicionid),
            'requisicion_numero': art.requisicion.cr8ca_requisicion,
            'cantidad': float(art.cr8ca_cantidad),
            'proveedor': art.proveedor.nombre if art.proveedor else '',
        })
        sin_material.append(art)

    # Artículos con material ya vinculado (histórico)
    con_material = ArticuloRequisicion.objects.filter(
        material__isnull=False
    ).select_related(
        'requisicion',
        'requisicion__usuario_solicitante',
        'proveedor',
        'material'
    ).order_by('-requisicion__fecha')[:50]

    categorias = CategoriaMaterial.objects.all().order_by('nombre')
    unidades = UnidadMedida.objects.all().order_by('nombre')
    ubicaciones = Ubicacion.objects.filter(Q(tipo='BODEGA') | Q(es_almacen=True)).order_by('nombre')
    marcas = Marca.objects.all().order_by('nombre')

    total_sin = len(sin_material)
    total_con = ArticuloRequisicion.objects.filter(material__isnull=False).count()
    context = {
        'sin_material': sin_material,
        'con_material': con_material,
        'total_pendientes': total_sin,
        'total_vinculados': total_con,
        'total_general': total_sin + total_con,
        'categorias': categorias,
        'unidades': unidades,
        'ubicaciones': ubicaciones,
        'marcas': marcas,
        'active_tab': 'nuevos_materiales',
        'title': 'Solicitud de Nuevos Materiales',
    }
    return render(request, 'inventarios/solicitud_nuevos_materiales.html', context)

@login_required
@staff_member_required
def admin_catalogos(request):
    from .models import CategoriaMaterial, UnidadMedida
    from activos.models import Marca
    from django.db.models import Q
    from django.contrib import messages

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'add_categoria':
                nombre = request.POST.get('nombre', '').strip()
                padre_id = request.POST.get('padre_id') or None
                descripcion = request.POST.get('descripcion', '').strip()
                if not nombre:
                    return JsonResponse({'status': 'error', 'message': 'El nombre es obligatorio'})
                padre = CategoriaMaterial.objects.filter(id=padre_id).first() if padre_id else None
                cat = CategoriaMaterial.objects.create(nombre=nombre, padre=padre, descripcion=descripcion)
                return JsonResponse({'status': 'success', 'id': cat.id, 'nombre': str(cat)})

            elif action == 'add_unidad':
                nombre = request.POST.get('nombre', '').strip()
                abreviatura = request.POST.get('abreviatura', '').strip()
                if not nombre or not abreviatura:
                    return JsonResponse({'status': 'error', 'message': 'Nombre y abreviatura son obligatorios'})
                uni = UnidadMedida.objects.create(nombre=nombre, abreviatura=abreviatura)
                return JsonResponse({'status': 'success', 'id': uni.id, 'nombre': str(uni)})

            elif action == 'add_marca':
                nombre = request.POST.get('nombre', '').strip()
                if not nombre:
                    return JsonResponse({'status': 'error', 'message': 'El nombre es obligatorio'})
                marca = Marca.objects.create(nombre=nombre)
                return JsonResponse({'status': 'success', 'id': marca.id, 'nombre': marca.nombre})

            elif action == 'delete_categoria':
                pk = request.POST.get('pk')
                CategoriaMaterial.objects.filter(id=pk).delete()
                return JsonResponse({'status': 'success'})

            elif action == 'delete_unidad':
                pk = request.POST.get('pk')
                UnidadMedida.objects.filter(id=pk).delete()
                return JsonResponse({'status': 'success'})

            elif action == 'delete_marca':
                pk = request.POST.get('pk')
                Marca.objects.filter(id=pk).delete()
                return JsonResponse({'status': 'success'})

            return JsonResponse({'status': 'error', 'message': 'Acción no válida'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    categorias = CategoriaMaterial.objects.all().order_by('nombre')
    unidades = UnidadMedida.objects.all().order_by('nombre')
    marcas = Marca.objects.all().order_by('nombre')

    context = {
        'categorias': categorias,
        'unidades': unidades,
        'marcas': marcas,
        'active_tab': 'admin_catalogos',
        'title': 'Administrar Catálogos',
    }
    return render(request, 'inventarios/admin_catalogos.html', context)


# ─── Calendario de Almacén ─────────────────────────────────────────────────

@login_required
def calendario_view(request):
    from django.contrib.auth.models import User
    es_almacen = request.user.groups.filter(name='Almacenes').exists() or request.user.is_superuser
    usuarios_almacen = User.objects.filter(groups__name='Almacenes', is_active=True).order_by('first_name')
    context = {
        'es_almacen': es_almacen,
        'usuarios_almacen': usuarios_almacen,
        'active_tab': 'calendario',
        'title': 'Calendario de Recepciones - Almacén',
    }
    return render(request, 'inventarios/calendario.html', context)


@login_required
def api_calendario_eventos(request):
    from datetime import datetime, timedelta
    from .models import SlotAlmacenCalendario
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    events = []
    try:
        start = datetime.strptime(start_str[:10], '%Y-%m-%d').date() if start_str else None
        end = datetime.strptime(end_str[:10], '%Y-%m-%d').date() if end_str else None
    except (ValueError, TypeError):
        start = end = None
    if not start or not end:
        from django.utils import timezone
        today = timezone.localdate()
        start = today - timedelta(days=30)
        end = today + timedelta(days=60)

    # 1. Requisiciones con fecha_probable_entrega
    try:
        from presupuestos.models import Requisicion
        requisiciones = Requisicion.objects.filter(
            recepcion_notificada=True,
            fecha_probable_entrega__isnull=False,
            fecha_probable_entrega__gte=start,
            fecha_probable_entrega__lte=end,
        ).select_related('usuario_solicitante', 'proveedor')
        # Prefetch slots vinculados a requisiciones
        req_ids = [r.cr8ca_requisicionid for r in requisiciones]
        slots_por_req = {}
        if req_ids:
            for s in SlotAlmacenCalendario.objects.filter(requisicion_id__in=req_ids).exclude(estado='CANCELADO'):
                slots_por_req[str(s.requisicion_id)] = s.id
        for req in requisiciones:
            f = req.fecha_probable_entrega
            req_uuid = str(req.cr8ca_requisicionid)
            slot_id = slots_por_req.get(req_uuid)
            events.append({
                'id': f'req-{req_uuid}',
                'title': f'Entrega: {req.cr8ca_requisicion}',
                'start': f.isoformat(),
                'end': f.isoformat(),
                'allDay': True,
                'backgroundColor': '#0a6ed1',
                'borderColor': '#0a6ed1',
                'textColor': '#fff',
                'extendedProps': {
                    'tipo': 'entrega_notificada',
                    'requisicion_uuid': req_uuid,
                    'requisicion': req.cr8ca_requisicion,
                    'asunto': req.cr8ca_asunto or '',
                    'proveedor': str(req.proveedor) if req.proveedor else '',
                    'solicitante': req.usuario_solicitante.get_full_name() if req.usuario_solicitante else '',
                    'slot_id': slot_id,
                    'readOnly': True,
                },
            })
    except Exception:
        pass

    # 2. Slots del calendario
    slots = SlotAlmacenCalendario.objects.filter(
        fecha__gte=start, fecha__lte=end,
    ).exclude(estado='CANCELADO').select_related('creado_por', 'asignado_a', 'requisicion')

    COLORS = {
        'ENTREGA': '#10b981',
        'RECOLECCION': '#f59e0b',
        'INVENTARIO': '#8b5cf6',
        'CAPACITACION': '#3b82f6',
        'OTRO': '#64748b',
    }
    for s in slots:
        color = COLORS.get(s.tipo, '#64748b')
        if s.estado == 'PENDIENTE':
            border = color
            bg = '#fff'
            txt = color
        elif s.estado == 'COMPLETADO':
            bg = '#d1fae5'
            border = '#10b981'
            txt = '#065f46'
        else:
            bg = color
            border = color
            txt = '#fff'
        start_dt = f'{s.fecha.isoformat()}T{s.hora_inicio.isoformat()}'
        end_dt = f'{s.fecha.isoformat()}T{s.hora_fin.isoformat()}'
        events.append({
            'id': f'slot-{s.id}',
            'title': s.titulo,
            'start': start_dt,
            'end': end_dt,
            'backgroundColor': bg,
            'borderColor': border,
            'textColor': txt,
            'extendedProps': {
                'tipo': 'slot',
                'slot_id': s.id,
                'descripcion': s.descripcion or '',
                'tipo_slot': s.tipo,
                'estado': s.estado,
                'creado_por': s.creado_por.get_full_name() or s.creado_por.username,
                'asignado_a': s.asignado_a.get_full_name() if s.asignado_a else '',
                'requisicion': str(s.requisicion) if s.requisicion else '',
                'readOnly': s.estado != 'PENDIENTE' or (s.creado_por != request.user and not request.user.groups.filter(name='Almacenes').exists() and not request.user.is_superuser),
            },
        })

    # 3. Disponibilidad diaria (bloque rojo de ocupado)
    try:
        from .models import DisponibilidadDiaria
        bloques = DisponibilidadDiaria.objects.filter(
            fecha__gte=start, fecha__lte=end, activo=True,
        ).select_related('usuario')
        for b in bloques:
            start_dt = f'{b.fecha.isoformat()}T{b.hora_inicio.isoformat()}'
            end_dt = f'{b.fecha.isoformat()}T{b.hora_fin.isoformat()}'
            events.append({
                'id': f'disp-{b.id}',
                'title': '🏴 Ocupado',
                'start': start_dt,
                'end': end_dt,
                'backgroundColor': '#fee2e2',
                'borderColor': '#ef4444',
                'textColor': '#dc2626',
                'display': 'block',
                'extendedProps': {
                    'tipo': 'disponibilidad',
                    'disp_id': b.id,
                    'usuario': b.usuario.get_full_name() or b.usuario.username,
                    'readOnly': True,
                },
            })
    except Exception:
        pass

    return JsonResponse(events, safe=False)


@login_required
@csrf_exempt
def api_calendario_slots(request, slot_id=None):
    from .models import SlotAlmacenCalendario
    import json as j
    es_almacen = request.user.groups.filter(name='Almacenes').exists() or request.user.is_superuser

    if request.method == 'GET' and slot_id:
        s = get_object_or_404(SlotAlmacenCalendario, id=slot_id)
        return JsonResponse({
            'id': s.id,
            'titulo': s.titulo,
            'descripcion': s.descripcion,
            'fecha': s.fecha.isoformat(),
            'hora_inicio': s.hora_inicio.isoformat(),
            'hora_fin': s.hora_fin.isoformat(),
            'tipo': s.tipo,
            'estado': s.estado,
            'asignado_a_id': s.asignado_a_id,
            'requisicion_id': str(s.requisicion_id) if s.requisicion_id else '',
            'creado_por': s.creado_por.get_full_name() or s.creado_por.username,
        })

    if request.method in ('POST', 'PUT'):
        data = j.loads(request.body)
        titulo = data.get('titulo', '').strip()
        if not titulo:
            return JsonResponse({'success': False, 'message': 'El título es obligatorio.'}, status=400)
        try:
            from datetime import datetime as dt
            fecha = dt.strptime(data['fecha'], '%Y-%m-%d').date()
            hora_inicio = dt.strptime(data['hora_inicio'], '%H:%M').time()
            hora_fin = dt.strptime(data['hora_fin'], '%H:%M').time()
        except (KeyError, ValueError) as e:
            return JsonResponse({'success': False, 'message': f'Fecha/hora inválida: {e}'}, status=400)
        if hora_fin <= hora_inicio:
            return JsonResponse({'success': False, 'message': 'La hora fin debe ser posterior a la hora inicio.'}, status=400)
        if slot_id:
            s = get_object_or_404(SlotAlmacenCalendario, id=slot_id)
            if not es_almacen and s.creado_por != request.user:
                return JsonResponse({'success': False, 'message': 'No tienes permiso para editar este slot.'}, status=403)
        else:
            s = SlotAlmacenCalendario(creado_por=request.user, estado='PENDIENTE')
        s.titulo = titulo
        s.descripcion = data.get('descripcion', '')
        s.fecha = fecha
        s.hora_inicio = hora_inicio
        s.hora_fin = hora_fin
        s.tipo = data.get('tipo', 'OTRO')
        if es_almacen:
            if 'estado' in data:
                s.estado = data['estado']
            if 'asignado_a_id' in data and data['asignado_a_id']:
                from django.contrib.auth.models import User
                s.asignado_a = User.objects.filter(id=data['asignado_a_id']).first()
        req_uuid = data.get('requisicion_uuid', '').strip()
        if req_uuid:
            try:
                from uuid import UUID
                from presupuestos.models import Requisicion
                s.requisicion = Requisicion.objects.filter(cr8ca_requisicionid=UUID(req_uuid)).first()
            except Exception:
                pass
        if not s.asignado_a_id and es_almacen:
            s.asignado_a = request.user
        s.save()
        return JsonResponse({'success': True, 'message': 'Slot guardado.', 'id': s.id})

    if request.method == 'DELETE' and slot_id:
        s = get_object_or_404(SlotAlmacenCalendario, id=slot_id)
        if not es_almacen and s.creado_por != request.user:
            return JsonResponse({'success': False, 'message': 'No tienes permiso para eliminar este slot.'}, status=403)
        s.delete()
        return JsonResponse({'success': True, 'message': 'Slot eliminado.'})

    return JsonResponse({'success': False, 'message': 'Método no permitido.'}, status=405)


@login_required
@csrf_exempt
def api_calendario_horarios(request):
    from .models import HorarioAlmacen
    import json as j
    es_almacen = request.user.groups.filter(name='Almacenes').exists() or request.user.is_superuser
    if not es_almacen:
        return JsonResponse({'success': False, 'message': 'Solo el personal de Almacenes puede gestionar horarios.'}, status=403)

    if request.method == 'GET':
        queryset = HorarioAlmacen.objects.filter(usuario=request.user, activo=True).order_by('dia_semana', 'hora_inicio')
        data = [{
            'id': h.id,
            'dia_semana': h.dia_semana,
            'hora_inicio': h.hora_inicio.isoformat(),
            'hora_fin': h.hora_fin.isoformat(),
        } for h in queryset]
        return JsonResponse(data, safe=False)

    if request.method == 'POST':
        data = j.loads(request.body)
        horarios = data.get('horarios', [])
        with transaction.atomic():
            HorarioAlmacen.objects.filter(usuario=request.user).delete()
            for h in horarios:
                dia = h.get('dia_semana')
                hi = h.get('hora_inicio')
                hf = h.get('hora_fin')
                if dia is not None and hi and hf:
                    try:
                        from datetime import datetime as dt
                        hi_t = dt.strptime(hi, '%H:%M').time()
                        hf_t = dt.strptime(hf, '%H:%M').time()
                        HorarioAlmacen.objects.create(
                            usuario=request.user,
                            dia_semana=dia,
                            hora_inicio=hi_t,
                            hora_fin=hf_t,
                        )
                    except ValueError:
                        pass
        return JsonResponse({'success': True, 'message': 'Horarios guardados.'})

    return JsonResponse({'success': False, 'message': 'Método no permitido.'}, status=405)


@login_required
@csrf_exempt
def api_calendario_disponibilidad_diaria(request, fecha):
    from .models import DisponibilidadDiaria
    import json as j
    es_almacen = request.user.groups.filter(name='Almacenes').exists() or request.user.is_superuser
    if not es_almacen:
        return JsonResponse({'success': False, 'message': 'Solo almacenistas.'}, status=403)
    try:
        from datetime import datetime as dt
        fecha_obj = dt.strptime(fecha, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Fecha inválida.'}, status=400)
    if request.method == 'GET':
        bloques = DisponibilidadDiaria.objects.filter(usuario=request.user, fecha=fecha_obj, activo=True).order_by('hora_inicio')
        data = [{'id': b.id, 'hora_inicio': b.hora_inicio.isoformat()[:5], 'hora_fin': b.hora_fin.isoformat()[:5]} for b in bloques]
        return JsonResponse(data, safe=False)
    if request.method == 'POST':
        data = j.loads(request.body)
        bloques = data.get('bloques', [])
        with transaction.atomic():
            DisponibilidadDiaria.objects.filter(usuario=request.user, fecha=fecha_obj).delete()
            for b in bloques:
                hi = b.get('hora_inicio')
                hf = b.get('hora_fin')
                if hi and hf:
                    try:
                        hi_t = dt.strptime(hi, '%H:%M').time()
                        hf_t = dt.strptime(hf, '%H:%M').time()
                        DisponibilidadDiaria.objects.create(usuario=request.user, fecha=fecha_obj, hora_inicio=hi_t, hora_fin=hf_t)
                    except ValueError:
                        pass
        return JsonResponse({'success': True, 'message': 'Disponibilidad guardada.'})
    return JsonResponse({'success': False, 'message': 'Método no permitido.'}, status=405)


@login_required
def api_calendario_requisicion_items(request, pk):
    try:
        from presupuestos.models import Requisicion, ArticuloRequisicion
        req = get_object_or_404(Requisicion, cr8ca_requisicionid=pk)
        items = ArticuloRequisicion.objects.filter(requisicion=req).select_related('material', 'proveedor')
        data = {
            'requisicion': req.cr8ca_requisicion,
            'asunto': req.cr8ca_asunto or '',
            'comentarios': req.cr8ca_comentarios or '',
            'proveedor': str(req.proveedor) if req.proveedor else '',
            'solicitante': req.usuario_solicitante.get_full_name() if req.usuario_solicitante else '',
            'fecha': req.fecha_probable_entrega.isoformat() if req.fecha_probable_entrega else '',
            'articulos': [{
                'descripcion': a.cr8ca_articulo,
                'cantidad': str(a.cr8ca_cantidad),
                'costo': str(a.cr8ca_costoaproximado) if a.cr8ca_costoaproximado else '',
                'material': str(a.material) if a.material else '',
                'proveedor': str(a.proveedor) if a.proveedor else '',
            } for a in items],
        }
        return JsonResponse(data)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════════════
# API: Materiales Utilizados por OT (vinculación OT ↔ Activo ↔ Material)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def api_materiales_utilizados_ot(request, ot_id):
    """
    GET: Lista materiales utilizados en una OT, agrupados por activo.
    POST: Registra un nuevo material utilizado en la OT.
    """
    from .models import MaterialUtilizadoOT
    ot = get_object_or_404(OrdenTrabajo, pk=ot_id)

    if request.method == 'GET':
        registros = MaterialUtilizadoOT.objects.filter(
            orden_trabajo=ot
        ).select_related('material', 'activo', 'registrado_por').order_by('activo__nombre', '-fecha_registro')

        data = []
        for r in registros:
            data.append({
                'id': r.id,
                'material_id': r.material_id,
                'material_nombre': r.material.nombre,
                'material_sku': r.material.sku,
                'activo_id': r.activo_id,
                'activo_nombre': r.activo.nombre if r.activo else None,
                'activo_codigo': r.activo.codigo_interno if r.activo else None,
                'cantidad': float(r.cantidad),
                'comentario': r.comentario,
                'registrado_por': r.registrado_por.get_full_name() if r.registrado_por else None,
                'fecha': r.fecha_registro.strftime('%d/%m/%Y %H:%M'),
            })

        # También incluir activos de la OT para el selector
        activos_ot = [
            {'id': a.id, 'nombre': a.nombre, 'codigo': a.codigo_interno}
            for a in ot.activos.all()
        ]

        return JsonResponse({
            'status': 'success',
            'materiales': data,
            'activos_ot': activos_ot,
            'ot_codigo': ot.codigo_de_orden,
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)

        material_id = data.get('material_id')
        activo_id = data.get('activo_id')  # Opcional
        cantidad = data.get('cantidad')
        comentario = data.get('comentario', '')

        if not material_id or not cantidad:
            return JsonResponse({'status': 'error', 'message': 'material_id y cantidad son requeridos'}, status=400)

        try:
            material = Material.objects.get(pk=material_id)
        except Material.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Material no encontrado'}, status=404)

        activo = None
        if activo_id:
            from activos.models import Activo
            try:
                activo = Activo.objects.get(pk=activo_id)
            except Activo.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Activo no encontrado'}, status=404)

        registro = MaterialUtilizadoOT.objects.create(
            orden_trabajo=ot,
            material=material,
            activo=activo,
            cantidad=Decimal(str(cantidad)),
            comentario=comentario,
            registrado_por=request.user,
        )

        return JsonResponse({
            'status': 'success',
            'message': f'{material.nombre} x{cantidad} vinculado a OT {ot.codigo_de_orden}',
            'id': registro.id,
        })

    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@login_required
@csrf_exempt
def api_materiales_utilizados_ot_delete(request, registro_id):
    """Elimina un registro de material utilizado en OT."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    from .models import MaterialUtilizadoOT
    registro = get_object_or_404(MaterialUtilizadoOT, pk=registro_id)
    registro.delete()
    return JsonResponse({'status': 'success', 'message': 'Registro eliminado'})


@login_required
def api_historial_materiales_activo(request, activo_id):
    """
    Retorna el historial de todos los materiales que se han utilizado
    en un activo específico a lo largo de todas las OTs.
    """
    from .models import MaterialUtilizadoOT
    from activos.models import Activo

    activo = get_object_or_404(Activo, pk=activo_id)
    registros = MaterialUtilizadoOT.objects.filter(
        activo=activo
    ).select_related(
        'material', 'orden_trabajo', 'registrado_por'
    ).order_by('-fecha_registro')

    data = []
    for r in registros:
        data.append({
            'id': r.id,
            'material_nombre': r.material.nombre,
            'material_sku': r.material.sku,
            'cantidad': float(r.cantidad),
            'ot_codigo': r.orden_trabajo.codigo_de_orden,
            'ot_id': r.orden_trabajo.id,
            'ot_tipo': r.orden_trabajo.get_tipo_display(),
            'comentario': r.comentario,
            'registrado_por': r.registrado_por.get_full_name() if r.registrado_por else None,
            'fecha': r.fecha_registro.strftime('%d/%m/%Y %H:%M'),
        })

    return JsonResponse({
        'status': 'success',
        'activo': {'id': activo.id, 'nombre': activo.nombre, 'codigo': activo.codigo_interno},
        'historial': data,
        'total_registros': len(data),
    })


@login_required
def api_vincular_material_activo(request, material_id):
    """
    POST: Registra que un material fue utilizado en un activo a través de una OT.
    Body: { "activo_id": <int>, "orden_trabajo_id": <int>, "cantidad": <float>, "comentario": "" }
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    material = get_object_or_404(Material, pk=material_id)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)

    activo_id = data.get('activo_id')
    ot_id = data.get('orden_trabajo_id')
    cantidad = data.get('cantidad')
    comentario = data.get('comentario', '')

    if not ot_id or not cantidad:
        return JsonResponse({'status': 'error', 'message': 'orden_trabajo_id y cantidad son requeridos'}, status=400)

    ot = get_object_or_404(OrdenTrabajo, pk=ot_id)

    activo = None
    if activo_id:
        from activos.models import Activo
        activo = get_object_or_404(Activo, pk=activo_id)

    from .models import MaterialUtilizadoOT
    registro = MaterialUtilizadoOT.objects.create(
        orden_trabajo=ot,
        material=material,
        activo=activo,
        cantidad=Decimal(str(cantidad)),
        comentario=comentario,
        registrado_por=request.user,
    )

    return JsonResponse({
        'status': 'success',
        'message': f'{material.nombre} vinculado a {activo.nombre if activo else "OT"} ({ot.codigo_de_orden})',
        'id': registro.id,
    })


@login_required
def api_search_activos(request):
    """
    GET: Busca activos por nombre, código o serie. Retorna JSON.
    """
    from activos.models import Activo
    from django.db.models import Q

    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    activos = Activo.objects.filter(
        Q(nombre__icontains=q) |
        Q(codigo_interno__icontains=q) |
        Q(serie__icontains=q)
    ).select_related('ubicacion').only(
        'id', 'nombre', 'codigo_interno', 'serie', 'ubicacion'
    ).order_by('nombre')[:15]

    results = [{
        'id': a.id,
        'nombre': a.nombre,
        'codigo': a.codigo_interno,
        'serie': a.serie or '',
        'ubicacion': a.ubicacion.nombre if a.ubicacion else '',
        'text': f"{a.nombre} ({a.codigo_interno})",
    } for a in activos]

    return JsonResponse({'results': results})


# ─── Visualizador de Categorías de Materiales ──────────────────────────────────

@staff_member_required
def categorias_visualizer(request):
    """
    Visualizador jerárquico de Categorías de Materiales con su código de exoneración asociado.
    """
    from .models import CategoriaMaterial
    from presupuestos.models import CodigoExoneracion
    from django.db.models import Count, Q

    categorias = CategoriaMaterial.objects.select_related('padre', 'codigo_exoneracion').annotate(
        materiales_count=Count('materiales'),
        subcategorias_count=Count('subcategorias'),
    ).order_by('nombre')

    # Construir árbol jerárquico
    categorias_raiz = [c for c in categorias if c.padre is None]
    categorias_hijas = {}
    for c in categorias:
        if c.padre_id:
            categorias_hijas.setdefault(c.padre_id, []).append(c)

    # Códigos de exoneración disponibles para asignar
    codigos_exoneracion = CodigoExoneracion.objects.filter(activo=True).order_by('codigo')

    # Manejo de acciones POST (asignar/quitar código de exoneración)
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'assign_codigo':
                cat_id = request.POST.get('categoria_id')
                codigo_id = request.POST.get('codigo_id')
                cat = CategoriaMaterial.objects.get(id=cat_id)
                if codigo_id:
                    cat.codigo_exoneracion_id = codigo_id
                else:
                    cat.codigo_exoneracion = None
                cat.save()
                return JsonResponse({'status': 'success', 'message': 'Código asignado correctamente'})

            elif action == 'remove_codigo':
                cat_id = request.POST.get('categoria_id')
                cat = CategoriaMaterial.objects.get(id=cat_id)
                cat.codigo_exoneracion = None
                cat.save()
                return JsonResponse({'status': 'success', 'message': 'Código removido'})

            elif action == 'edit_categoria':
                cat_id = request.POST.get('categoria_id')
                cat = CategoriaMaterial.objects.get(id=cat_id)
                nombre = request.POST.get('nombre', '').strip()
                descripcion = request.POST.get('descripcion', '').strip()
                padre_id = request.POST.get('padre_id') or None
                codigo_id = request.POST.get('codigo_exoneracion_id') or None
                if not nombre:
                    return JsonResponse({'status': 'error', 'message': 'El nombre es obligatorio'})
                # Evitar asignarse a sí misma como padre
                if padre_id and int(padre_id) == cat.id:
                    return JsonResponse({'status': 'error', 'message': 'Una categoría no puede ser su propio padre'})
                cat.nombre = nombre
                cat.descripcion = descripcion or None
                cat.padre_id = padre_id
                cat.codigo_exoneracion_id = codigo_id
                cat.save()
                return JsonResponse({'status': 'success', 'message': 'Categoría actualizada', 'nombre': str(cat)})

            elif action == 'add_categoria':
                nombre = request.POST.get('nombre', '').strip()
                descripcion = request.POST.get('descripcion', '').strip()
                padre_id = request.POST.get('padre_id') or None
                codigo_id = request.POST.get('codigo_exoneracion_id') or None
                if not nombre:
                    return JsonResponse({'status': 'error', 'message': 'El nombre es obligatorio'})
                cat = CategoriaMaterial.objects.create(
                    nombre=nombre,
                    descripcion=descripcion or None,
                    padre_id=padre_id,
                    codigo_exoneracion_id=codigo_id,
                )
                return JsonResponse({'status': 'success', 'id': cat.id, 'nombre': str(cat), 'message': 'Categoría creada'})

            elif action == 'delete_categoria':
                cat_id = request.POST.get('categoria_id')
                cat = CategoriaMaterial.objects.get(id=cat_id)
                # Verificar si tiene materiales
                mat_count = cat.materiales.count()
                sub_count = cat.subcategorias.count()
                if mat_count > 0:
                    return JsonResponse({'status': 'error', 'message': f'No se puede eliminar: tiene {mat_count} materiales asociados'})
                if sub_count > 0:
                    return JsonResponse({'status': 'error', 'message': f'No se puede eliminar: tiene {sub_count} subcategorías'})
                cat.delete()
                return JsonResponse({'status': 'success', 'message': 'Categoría eliminada'})

            elif action == 'get_categoria':
                cat_id = request.POST.get('categoria_id')
                cat = CategoriaMaterial.objects.select_related('codigo_exoneracion').get(id=cat_id)
                return JsonResponse({
                    'status': 'success',
                    'data': {
                        'id': cat.id,
                        'nombre': cat.nombre,
                        'descripcion': cat.descripcion or '',
                        'padre_id': cat.padre_id,
                        'codigo_exoneracion_id': cat.codigo_exoneracion_id,
                        'codigo_exoneracion_str': str(cat.codigo_exoneracion) if cat.codigo_exoneracion else '',
                    }
                })

            elif action == 'get_material':
                mat_id = request.POST.get('material_id')
                mat = Material.objects.select_related('categoria', 'unidad_medida', 'marca', 'codigo_exoneracion').get(id=mat_id)
                return JsonResponse({
                    'status': 'success',
                    'data': {
                        'id': mat.id,
                        'nombre': mat.nombre,
                        'sku': mat.sku,
                        'descripcion': mat.descripcion or '',
                        'precio_estimado': str(mat.precio_estimado),
                        'stock_minimo': str(mat.stock_minimo),
                        'tipo_material': mat.tipo_material,
                        'categoria_id': mat.categoria_id,
                        'unidad_medida_id': mat.unidad_medida_id,
                        'unidad_medida_str': str(mat.unidad_medida) if mat.unidad_medida else '',
                        'marca_id': mat.marca_id,
                        'marca_str': str(mat.marca) if mat.marca else '',
                        'codigo_exoneracion_id': mat.codigo_exoneracion_id,
                        'codigo_exoneracion_str': str(mat.codigo_exoneracion) if mat.codigo_exoneracion else '',
                        'no_afecta_stock': mat.no_afecta_stock,
                    }
                })

            elif action == 'edit_material':
                mat_id = request.POST.get('material_id')
                mat = Material.objects.get(id=mat_id)
                nombre = request.POST.get('nombre', '').strip()
                sku = request.POST.get('sku', '').strip()
                if not nombre or not sku:
                    return JsonResponse({'status': 'error', 'message': 'Nombre y SKU son obligatorios'})
                if Material.objects.filter(sku=sku).exclude(id=mat.id).exists():
                    return JsonResponse({'status': 'error', 'message': f'El SKU "{sku}" ya está en uso'})
                mat.nombre = nombre
                mat.sku = sku
                mat.descripcion = request.POST.get('descripcion', '').strip() or None
                mat.precio_estimado = request.POST.get('precio_estimado') or 0
                mat.stock_minimo = request.POST.get('stock_minimo') or 0
                mat.tipo_material = request.POST.get('tipo_material', 'INSUMO')
                mat.categoria_id = request.POST.get('categoria_id') or None
                mat.unidad_medida_id = request.POST.get('unidad_medida_id') or None
                mat.codigo_exoneracion_id = request.POST.get('codigo_exoneracion_id') or None
                mat.no_afecta_stock = request.POST.get('no_afecta_stock') == 'true'
                mat.save()
                return JsonResponse({'status': 'success', 'message': 'Material actualizado'})

            return JsonResponse({'status': 'error', 'message': 'Acción no válida'})
        except CategoriaMaterial.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Categoría no encontrada'})
        except Material.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Material no encontrado'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    # Unidades de medida para el modal de material
    unidades = UnidadMedida.objects.all().order_by('nombre')

    context = {
        'categorias_raiz': categorias_raiz,
        'categorias_hijas': categorias_hijas,
        'categorias_all': categorias,
        'codigos_exoneracion': codigos_exoneracion,
        'unidades': unidades,
        'materiales_por_categoria': {
            c.id: list(c.materiales.values('id', 'sku', 'nombre', 'precio_estimado')[:20])
            for c in categorias
        },
        'active_tab': 'categorias_visualizer',
        'title': 'Visualizador de Categorías',
    }
    return render(request, 'inventarios/categorias_visualizer.html', context)


@login_required
def solicitud_detalle_rapido(request, pk):
    """Vista rápida de solicitud de material sin framework admin."""
    from .models import SolicitudMaterial, MovimientoInventario

    solicitud = get_object_or_404(
        SolicitudMaterial.objects.select_related(
            'usuario', 'ubicacion_origen', 'orden_trabajo', 'entregado_por',
            'edificio_destino', 'nivel_destino', 'ticket'
        ),
        pk=pk
    )

    items = MovimientoInventario.objects.filter(solicitud=solicitud).select_related(
        'material', 'material__unidad_medida', 'ubicacion_origen', 'ubicacion_destino', 'usuario'
    ).order_by('fecha_movimiento')

    context = {
        'sol': solicitud,
        'items': items,
    }
    return render(request, 'inventarios/solicitud_detalle_rapido.html', context)


@login_required
def solicitud_update_rapido(request, pk):
    """API para actualizar estado y comentarios de una solicitud."""
    import json
    from .models import SolicitudMaterial

    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    solicitud = get_object_or_404(SolicitudMaterial, pk=pk)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    # Actualizar campos editables
    if 'estado' in data:
        solicitud.estado = data['estado']
    if 'comentarios_almacen' in data:
        solicitud.comentarios_almacen = data['comentarios_almacen']
    if 'comentarios_solicitud' in data:
        solicitud.comentarios_solicitud = data['comentarios_solicitud']
    if 'orden_trabajo_id' in data:
        ot_id = data['orden_trabajo_id']
        if ot_id:
            from mantenimiento.models import OrdenTrabajo
            solicitud.orden_trabajo = OrdenTrabajo.objects.filter(id=ot_id).first()
        else:
            solicitud.orden_trabajo = None
    if 'ticket_id' in data:
        ticket_id = data['ticket_id']
        if ticket_id:
            from callcenter.models import SolicitudTicket
            solicitud.ticket = SolicitudTicket.objects.filter(id=ticket_id).first()
        else:
            solicitud.ticket = None

    # Remove item action
    if data.get('action') == 'remove_item':
        item_id = data.get('item_id')
        if item_id:
            from .models import MovimientoInventario
            MovimientoInventario.objects.filter(id=item_id, solicitud=solicitud).delete()
            return JsonResponse({'status': 'success', 'message': 'Item eliminado'})

    solicitud.save()
    return JsonResponse({'status': 'success', 'estado': solicitud.get_estado_display()})


@login_required
def api_search_marcas(request):
    """
    GET: Busca marcas por nombre para autocompletado.
    Parámetro ?q= con mínimo 1 caracter.
    Si ?q está vacío devuelve las primeras 20 marcas.
    """
    from activos.models import Marca
    from django.db.models import Q

    q = request.GET.get('q', '').strip()
    
    if q:
        marcas = Marca.objects.filter(nombre__icontains=q).order_by('nombre')[:20]
    else:
        marcas = Marca.objects.all().order_by('nombre')[:20]

    results = [{
        'id': m.id,
        'nombre': m.nombre,
    } for m in marcas]

    return JsonResponse({'results': results})


@login_required
def ajuste_masivo_view(request):
    """
    Vista para importar un archivo CSV con SKU y cantidades actuales
    para realizar un ajuste masivo de inventario.
    Solo accesible para usuarios del grupo Auditoria o superusuarios.
    """
    from django.db.models import Q
    from .models import AjusteMasivoInventario

    # Verificar pertenencia al grupo Auditoria o Procura_Tecnica
    es_auditoria = request.user.groups.filter(name='Auditoria').exists() or request.user.is_superuser
    puede_asignar_depto = request.user.groups.filter(name='Procura_Tecnica').exists() or request.user.is_superuser
    if not (es_auditoria or puede_asignar_depto):
        messages.error(request, 'No tienes permiso para acceder a esta sección.')
        return redirect('inventarios:dashboard')

    ubicaciones = Ubicacion.objects.filter(Q(tipo='BODEGA') | Q(es_almacen=True)).order_by('nombre')
    historial = AjusteMasivoInventario.objects.filter(usuario=request.user).order_by('-fecha')[:20]
    categorias = CategoriaMaterial.objects.all().order_by('nombre')

    from core.models import Departamento
    departamentos = Departamento.objects.all().order_by('nombre')

    context = {
        'ubicaciones': ubicaciones,
        'historial': historial,
        'categorias': categorias,
        'departamentos': departamentos,
        'tipos_material': Material.TIPO_MATERIAL_CHOICES,
        'active_tab': 'ajuste_masivo',
        'title': 'Ajuste Masivo de Inventario',
        'es_auditoria': es_auditoria,
        'puede_asignar_depto': puede_asignar_depto,
    }
    return render(request, 'inventarios/ajuste_masivo.html', context)


@login_required
@csrf_exempt
def api_ajuste_masivo_procesar(request):
    """
    Procesa un archivo CSV con SKU y cantidades para ajustar el inventario.
    Formato esperado: SKU, Cantidad
    La cantidad es la cantidad ACTUAL (conteo físico), se calcula la diferencia.
    """
    import csv
    import io
    from .models import AjusteMasivoInventario

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    # Verificar pertenencia al grupo Auditoria
    es_auditoria = request.user.groups.filter(name='Auditoria').exists() or request.user.is_superuser
    if not es_auditoria:
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)

    ubicacion_id = request.POST.get('ubicacion_id')
    archivo = request.FILES.get('archivo_csv')
    comentarios = request.POST.get('comentarios', '')

    if not ubicacion_id:
        return JsonResponse({'status': 'error', 'message': 'Debe seleccionar una ubicación/bodega.'}, status=400)

    if not archivo:
        return JsonResponse({'status': 'error', 'message': 'Debe cargar un archivo CSV.'}, status=400)

    try:
        ubicacion = Ubicacion.objects.get(pk=ubicacion_id)
    except Ubicacion.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Ubicación no encontrada.'}, status=404)

    # Leer el CSV
    try:
        contenido = archivo.read().decode('utf-8-sig')
        reader = csv.reader(io.StringIO(contenido))
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error al leer el archivo: {str(e)}'}, status=400)

    # Crear registro del ajuste masivo
    ajuste = AjusteMasivoInventario.objects.create(
        usuario=request.user,
        ubicacion=ubicacion,
        archivo_csv=archivo,
        comentarios=comentarios,
    )

    log_resultado = []
    total_procesados = 0
    total_ajustados = 0
    total_errores = 0

    with transaction.atomic():
        for row_num, row in enumerate(reader, start=1):
            # Saltar header si existe
            if row_num == 1:
                # Detectar si la primera fila es un header
                if row and row[0].strip().upper() in ['SKU', 'CODIGO', 'CÓDIGO', 'COD']:
                    continue

            if not row or len(row) < 2:
                log_resultado.append({
                    'fila': row_num,
                    'sku': '',
                    'status': 'error',
                    'mensaje': 'Fila vacía o incompleta'
                })
                total_errores += 1
                continue

            sku = row[0].strip()
            try:
                cantidad_actual = Decimal(row[1].strip().replace(',', '.'))
            except (InvalidOperation, ValueError):
                log_resultado.append({
                    'fila': row_num,
                    'sku': sku,
                    'status': 'error',
                    'mensaje': f'Cantidad inválida: "{row[1].strip()}"'
                })
                total_errores += 1
                continue

            if cantidad_actual < 0:
                log_resultado.append({
                    'fila': row_num,
                    'sku': sku,
                    'status': 'error',
                    'mensaje': 'La cantidad no puede ser negativa'
                })
                total_errores += 1
                continue

            # Buscar material por SKU
            material = Material.objects.filter(sku=sku).first()
            if not material:
                log_resultado.append({
                    'fila': row_num,
                    'sku': sku,
                    'status': 'error',
                    'mensaje': 'Material no encontrado'
                })
                total_errores += 1
                continue

            total_procesados += 1

            # Obtener stock actual en la ubicación
            stock_record = StockRecord.objects.filter(
                material=material,
                ubicacion=ubicacion,
                lote=None,
                ubicacion_especifica=''
            ).first()

            stock_sistema = stock_record.cantidad if stock_record else Decimal('0.00')
            diferencia = cantidad_actual - stock_sistema

            if diferencia == 0:
                log_resultado.append({
                    'fila': row_num,
                    'sku': sku,
                    'material': material.nombre,
                    'status': 'sin_cambio',
                    'stock_sistema': float(stock_sistema),
                    'cantidad_conteo': float(cantidad_actual),
                    'diferencia': 0,
                    'mensaje': 'Sin diferencia, no se ajustó'
                })
                continue

            # Crear movimiento de ajuste
            if diferencia > 0:
                # Hay más material del que dice el sistema → entrada de ajuste
                MovimientoInventario.objects.create(
                    material=material,
                    tipo='AJUSTE',
                    cantidad=abs(diferencia),
                    ubicacion_destino=ubicacion,
                    usuario=request.user,
                    estado='APROBADO',
                    aprobado_por=request.user,
                    fecha_aprobacion=timezone.now(),
                    comentarios=f'Ajuste masivo #{ajuste.id} - Conteo físico: {cantidad_actual}, Sistema: {stock_sistema}'
                )
            else:
                # Hay menos material del que dice el sistema → salida de ajuste
                MovimientoInventario.objects.create(
                    material=material,
                    tipo='AJUSTE',
                    cantidad=abs(diferencia),
                    ubicacion_origen=ubicacion,
                    usuario=request.user,
                    estado='APROBADO',
                    aprobado_por=request.user,
                    fecha_aprobacion=timezone.now(),
                    comentarios=f'Ajuste masivo #{ajuste.id} - Conteo físico: {cantidad_actual}, Sistema: {stock_sistema}'
                )

            total_ajustados += 1
            log_resultado.append({
                'fila': row_num,
                'sku': sku,
                'material': material.nombre,
                'status': 'ajustado',
                'stock_sistema': float(stock_sistema),
                'cantidad_conteo': float(cantidad_actual),
                'diferencia': float(diferencia),
                'mensaje': f'Ajustado: {stock_sistema} → {cantidad_actual} (dif: {"+" if diferencia > 0 else ""}{diferencia})'
            })

    # Actualizar registro del ajuste masivo
    ajuste.total_procesados = total_procesados
    ajuste.total_ajustados = total_ajustados
    ajuste.total_errores = total_errores
    ajuste.log_resultado = log_resultado
    ajuste.save()

    return JsonResponse({
        'status': 'success',
        'message': f'Ajuste masivo completado. {total_procesados} procesados, {total_ajustados} ajustados, {total_errores} errores.',
        'ajuste_id': ajuste.id,
        'total_procesados': total_procesados,
        'total_ajustados': total_ajustados,
        'total_errores': total_errores,
        'log': log_resultado,
    })


@login_required
def api_ajuste_masivo_catalogo(request):
    """
    API paginada para listar todos los materiales con stock y bodega.
    Soporta búsqueda por texto y filtros por categoría, bodega y tipo.
    Solo accesible para usuarios del grupo Auditoria o superusuarios.
    """
    from django.db.models import Q, Sum, Prefetch
    from django.core.paginator import Paginator

    es_auditoria = request.user.groups.filter(name='Auditoria').exists() or request.user.is_superuser
    if not es_auditoria:
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)

    # Parámetros
    search = request.GET.get('q', '').strip()
    categoria_id = request.GET.get('categoria')
    bodega_id = request.GET.get('bodega')
    tipo = request.GET.get('tipo')
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 50))

    qs = Material.objects.select_related('categoria', 'unidad_medida', 'marca').prefetch_related('departamentos').all()

    # Filtros
    if search:
        qs = qs.filter(
            Q(nombre__icontains=search) |
            Q(sku__icontains=search) |
            Q(descripcion__icontains=search)
        )

    if categoria_id:
        qs = qs.filter(categoria_id=categoria_id)

    if tipo:
        qs = qs.filter(tipo_material=tipo)

    if bodega_id:
        qs = qs.filter(existencias__ubicacion_id=bodega_id, existencias__cantidad__gt=0).distinct()

    qs = qs.order_by('nombre')

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page)

    # Obtener IDs de materiales en la página actual
    materiales_page = list(page_obj)
    material_ids = [m.id for m in materiales_page]

    # Pre-cargar existencias agrupadas por material
    from collections import defaultdict
    stock_by_material = defaultdict(list)
    existencias = StockRecord.objects.filter(
        material_id__in=material_ids, cantidad__gt=0
    ).select_related('ubicacion').values(
        'material_id', 'ubicacion__nombre', 'cantidad'
    )
    for ex in existencias:
        stock_by_material[ex['material_id']].append({
            'bodega': ex['ubicacion__nombre'],
            'cantidad': float(ex['cantidad']),
        })

    # Construir respuesta
    items = []
    for m in materiales_page:
        bodegas = stock_by_material.get(m.id, [])
        stock_total = sum(b['cantidad'] for b in bodegas)
        bodegas_nombres = ', '.join(set(b['bodega'] for b in bodegas)) if bodegas else '—'

        deptos = list(m.departamentos.all())
        items.append({
            'id': m.id,
            'sku': m.sku,
            'nombre': m.nombre,
            'categoria': m.categoria.nombre if m.categoria else 'Sin categoría',
            'tipo': m.get_tipo_material_display(),
            'unidad': m.unidad_medida.abreviatura if m.unidad_medida else '—',
            'stock_total': stock_total,
            'stock_minimo': float(m.stock_minimo),
            'bodegas': bodegas_nombres,
            'bodegas_detalle': bodegas,
            'bajo_stock': stock_total < float(m.stock_minimo) and float(m.stock_minimo) > 0,
            'departamentos': ', '.join(d.nombre for d in deptos) if deptos else 'Global',
            'departamentos_ids': [d.id for d in deptos],
        })

    return JsonResponse({
        'status': 'success',
        'items': items,
        'page': page_obj.number,
        'total_pages': paginator.num_pages,
        'total_items': paginator.count,
        'has_next': page_obj.has_next(),
        'has_prev': page_obj.has_previous(),
    })


@login_required
def api_ajuste_masivo_asignar_departamento(request):
    """
    Asigna (o reemplaza) el departamento de una lista de materiales.
    Solo accesible para usuarios del grupo Auditoria o superusuarios.

    Body JSON:
      {
        "material_ids": [1, 2, 3],
        "departamento_id": 5,        # departamento a asignar
        "modo": "agregar" | "reemplazar"  # opcional, por defecto "agregar"
      }
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    # Solo el grupo Procura_Tecnica o un superusuario puede asignar departamentos.
    puede_asignar = request.user.groups.filter(name='Procura_Tecnica').exists() or request.user.is_superuser
    if not puede_asignar:
        return JsonResponse({'status': 'error', 'message': 'No autorizado. Solo Procura Técnica puede asignar materiales a departamentos.'}, status=403)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)

    material_ids = data.get('material_ids') or []
    departamento_id = data.get('departamento_id')
    modo = (data.get('modo') or 'agregar').lower()

    if not material_ids:
        return JsonResponse({'status': 'error', 'message': 'No se seleccionó ningún material.'}, status=400)
    if not departamento_id:
        return JsonResponse({'status': 'error', 'message': 'Debe seleccionar un departamento.'}, status=400)

    from core.models import Departamento
    departamento = Departamento.objects.filter(id=departamento_id).first()
    if not departamento:
        return JsonResponse({'status': 'error', 'message': 'El departamento no existe.'}, status=404)

    materiales = Material.objects.filter(id__in=material_ids)
    actualizados = 0
    for m in materiales:
        if modo == 'reemplazar':
            m.departamentos.set([departamento])
        else:
            m.departamentos.add(departamento)
        actualizados += 1

    return JsonResponse({
        'status': 'success',
        'message': f"{actualizados} material(es) asignado(s) al departamento '{departamento.nombre}'.",
        'actualizados': actualizados,
        'departamento': departamento.nombre,
    })


@login_required
def api_ajuste_masivo_asignar_categoria(request):
    """
    Cambia la categoría de una lista de materiales.
    Solo accesible para el grupo Procura_Tecnica o superusuarios.

    Body JSON:
      {
        "material_ids": [1, 2, 3],
        "categoria_id": 5
      }
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    # Solo el grupo Procura_Tecnica o un superusuario puede cambiar categorías.
    puede_asignar = request.user.groups.filter(name='Procura_Tecnica').exists() or request.user.is_superuser
    if not puede_asignar:
        return JsonResponse({'status': 'error', 'message': 'No autorizado. Solo Procura Técnica puede cambiar la categoría de los materiales.'}, status=403)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)

    material_ids = data.get('material_ids') or []
    categoria_id = data.get('categoria_id')

    if not material_ids:
        return JsonResponse({'status': 'error', 'message': 'No se seleccionó ningún material.'}, status=400)
    if not categoria_id:
        return JsonResponse({'status': 'error', 'message': 'Debe seleccionar una categoría.'}, status=400)

    categoria = CategoriaMaterial.objects.filter(id=categoria_id).first()
    if not categoria:
        return JsonResponse({'status': 'error', 'message': 'La categoría no existe.'}, status=404)

    actualizados = Material.objects.filter(id__in=material_ids).update(categoria=categoria)

    return JsonResponse({
        'status': 'success',
        'message': f"{actualizados} material(es) movido(s) a la categoría '{categoria.nombre}'.",
        'actualizados': actualizados,
        'categoria': categoria.nombre,
    })


@csrf_exempt
def solicitud_autorizar_publica(request, pk):
    """
    Autoriza o rechaza una solicitud de material desde el correo (enlace simple sin login).
    Uso: /inventarios/api/solicitudes/<pk>/autorizar/?accion=aprobar|rechazar&aprobador=<user_id>

    - El primer aprobador que actúe cierra la solicitud.
    - Si la solicitud ya fue resuelta, muestra quién la aprobó/rechazó y cuándo.
    Devuelve una página HTML de confirmación pensada para abrirse desde el correo.
    """
    from django.contrib.auth import get_user_model
    from django.utils import timezone

    solicitud = get_object_or_404(SolicitudMaterial, pk=pk)
    accion = (request.GET.get('accion') or '').lower()
    aprobador_id = request.GET.get('aprobador')

    User = get_user_model()
    aprobador = User.objects.filter(id=aprobador_id).first() if aprobador_id else None

    def _nombre(u):
        return (u.get_full_name() or u.username) if u else 'Un aprobador'

    def _pagina(titulo, mensaje, color):
        html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titulo}</title>
<style>
body {{ font-family:'Segoe UI',Arial,sans-serif; background:#eff2f5; margin:0; padding:0; }}
.box {{ max-width:520px; margin:60px auto; background:#fff; border:1px solid #d9d9d9; border-radius:8px; overflow:hidden; box-shadow:0 4px 12px rgba(0,0,0,0.08); }}
.hd {{ background:{color}; color:#fff; padding:22px 28px; font-size:1.15rem; font-weight:700; }}
.bd {{ padding:26px 28px; color:#32363a; font-size:0.98rem; line-height:1.6; }}
.sol {{ color:#6a6d70; font-size:0.85rem; margin-top:14px; }}
a.btn {{ display:inline-block; margin-top:18px; background:#0070f2; color:#fff; text-decoration:none; padding:10px 22px; border-radius:4px; font-weight:600; font-size:0.9rem; }}
</style></head><body>
<div class="box"><div class="hd">{titulo}</div>
<div class="bd">{mensaje}
<div class="sol">Solicitud #{solicitud.id} · Solicitante: {solicitud.solicitante_nombre}</div>
<a class="btn" href="{'/inventarios/mobile/pedidos/' + str(solicitud.id) + '/'}">Ver detalle de la solicitud</a>
</div></div></body></html>"""
        return HttpResponse(html)

    # Si ya fue resuelta previamente, informar el resultado existente
    if solicitud.estado == 'PENDIENTE' and solicitud.autorizado_por:
        fecha = solicitud.fecha_autorizacion.strftime('%d/%m/%Y %H:%M') if solicitud.fecha_autorizacion else ''
        return _pagina(
            'Solicitud ya autorizada',
            f"Esta solicitud ya fue <strong>autorizada por {_nombre(solicitud.autorizado_por)}</strong>{(' el ' + fecha) if fecha else ''}. No se requiere acción adicional.",
            '#107e3e'
        )
    if solicitud.estado == 'RECHAZADO':
        fecha = solicitud.fecha_rechazo.strftime('%d/%m/%Y %H:%M') if solicitud.fecha_rechazo else ''
        return _pagina(
            'Solicitud rechazada',
            f"Esta solicitud fue <strong>rechazada por {_nombre(solicitud.rechazado_por)}</strong>{(' el ' + fecha) if fecha else ''}.",
            '#bb0000'
        )
    if solicitud.estado not in ('PENDIENTE_AUTORIZACION',):
        return _pagina(
            'Solicitud no disponible',
            f"Esta solicitud está en estado <strong>{solicitud.get_estado_display()}</strong> y no puede autorizarse desde aquí.",
            '#6a6d70'
        )

    # Procesar la acción
    if accion == 'aprobar':
        solicitud.estado = 'PENDIENTE'  # aprobada → pasa a pendiente de despacho en almacén
        solicitud.autorizado_por = aprobador
        solicitud.fecha_autorizacion = timezone.now()
        solicitud.save(update_fields=['estado', 'autorizado_por', 'fecha_autorizacion'])
        try:
            from .utils_ntfy import notificar_nueva_solicitud
            notificar_nueva_solicitud(solicitud)
        except Exception:
            pass
        # Notificar al departamento de Almacenes (aprobadores) que está lista para despacho
        try:
            from .utils_n8n import notify_powerautomate_almacen
            notify_powerautomate_almacen(solicitud)
        except Exception:
            pass
        return _pagina(
            'Solicitud autorizada',
            f"Gracias. La solicitud fue <strong>autorizada</strong> correctamente por <strong>{_nombre(aprobador)}</strong>. El almacén ha sido notificado.",
            '#107e3e'
        )
    elif accion == 'rechazar':
        solicitud.estado = 'RECHAZADO'
        solicitud.rechazado_por = aprobador
        solicitud.fecha_rechazo = timezone.now()
        solicitud.save(update_fields=['estado', 'rechazado_por', 'fecha_rechazo'])
        return _pagina(
            'Solicitud rechazada',
            f"La solicitud fue <strong>rechazada</strong> por <strong>{_nombre(aprobador)}</strong>. Se notificará al solicitante.",
            '#bb0000'
        )
    else:
        return _pagina(
            'Acción no válida',
            "El enlace no especifica una acción válida (aprobar o rechazar).",
            '#e9730c'
        )


def solicitud_estado_badge(request, pk):
    """
    Genera un badge PNG dinámico con el estado actual de la solicitud, para
    incrustar en el correo. Al abrir el correo, muestra el estado en vivo:
    'Pendiente de autorización' o 'Autorizada por {nombre} el {fecha}'.
    """
    from PIL import Image, ImageDraw, ImageFont
    from django.utils import timezone
    import io

    solicitud = SolicitudMaterial.objects.filter(pk=pk).select_related('autorizado_por', 'rechazado_por').first()

    # Determinar texto y color según el estado
    if not solicitud:
        texto, color = "Solicitud no encontrada", (106, 109, 112)
    elif solicitud.estado == 'RECHAZADO':
        nom = (solicitud.rechazado_por.get_full_name() or solicitud.rechazado_por.username) if solicitud.rechazado_por else 'un aprobador'
        fecha = solicitud.fecha_rechazo.strftime('%d/%m/%Y %H:%M') if solicitud.fecha_rechazo else ''
        texto, color = f"Rechazada por {nom}" + (f" el {fecha}" if fecha else ""), (187, 0, 0)
    elif solicitud.autorizado_por:
        nom = solicitud.autorizado_por.get_full_name() or solicitud.autorizado_por.username
        fecha = solicitud.fecha_autorizacion.strftime('%d/%m/%Y %H:%M') if solicitud.fecha_autorizacion else ''
        texto, color = f"Autorizada por {nom}" + (f" el {fecha}" if fecha else ""), (16, 126, 62)
    elif solicitud.estado == 'PENDIENTE_AUTORIZACION':
        texto, color = "Pendiente de autorización", (233, 115, 12)
    else:
        texto, color = f"Estado: {solicitud.get_estado_display()}", (0, 112, 242)

    # Construir la imagen
    try:
        font = ImageFont.truetype("arialbd.ttf", 20)
    except Exception:
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
        except Exception:
            font = ImageFont.load_default()

    pad_x, pad_y = 22, 12
    tmp = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(tmp)
    bbox = d.textbbox((0, 0), texto, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    w, h = tw + pad_x * 2, th + pad_y * 2

    img = Image.new("RGB", (w, h), color)
    draw = ImageDraw.Draw(img)
    draw.text((pad_x, pad_y - bbox[1]), texto, fill=(255, 255, 255), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    resp = HttpResponse(buf.getvalue(), content_type="image/png")
    # Evitar que el cliente de correo cachee un estado viejo
    resp['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp['Pragma'] = 'no-cache'
    resp['Expires'] = '0'
    return resp


@login_required
def dashboard_departamento(request):
    """
    Dashboard por departamento del usuario:
      1. Materiales permitidos de su departamento.
      2. Salidas (movimientos) aprobadas cuyos materiales pertenecen a su departamento.
    """
    from django.db.models import Sum
    from .models import Material, MovimientoInventario, SolicitudMaterial

    perfil = getattr(request.user, 'perfil', None)
    departamento = getattr(perfil, 'departamento', None)
    es_aprobador = bool(perfil and getattr(perfil, 'aprobador_salidas', False))

    solicitudes_pendientes = []
    total_salidas = 0
    total_pendientes = 0

    q = (request.GET.get('q') or '').strip()

    if departamento:
        # 1. Materiales de mi departamento (paginados + búsqueda, pueden ser miles)
        from django.core.paginator import Paginator
        from django.db.models import Q

        from django.db.models import Count

        # 1. Materiales MÁS UTILIZADOS por el equipo (top 10 por cantidad total solicitada)
        materiales_top = (
            MovimientoInventario.objects
            .filter(tipo='SALIDA', solicitud__usuario__perfil__departamento=departamento)
            .values('material__id', 'material__nombre', 'material__sku', 'material__unidad_medida__abreviatura')
            .annotate(
                total_cantidad=Sum('cantidad_solicitada'),
                veces=Count('id'),
            )
            .order_by('-total_cantidad')[:10]
        )
        total_materiales = MovimientoInventario.objects.filter(
            tipo='SALIDA', solicitud__usuario__perfil__departamento=departamento
        ).values('material_id').distinct().count()

        # 2. Salidas AGRUPADAS POR SOLICITUD hechas por el equipo (paginadas)
        salidas_qs = (
            SolicitudMaterial.objects
            .filter(usuario__perfil__departamento=departamento)
            .exclude(estado='BORRADOR')
            .select_related('usuario', 'orden_trabajo', 'ubicacion_origen')
            .annotate(num_items=Count('items'))
            .order_by('-fecha_solicitud')
        )
        if q:
            salidas_qs = salidas_qs.filter(
                Q(id__icontains=q) |
                Q(orden_trabajo__codigo_de_orden__icontains=q) |
                Q(comentarios_solicitud__icontains=q)
            )
        total_salidas = salidas_qs.count()
        salidas_paginator = Paginator(salidas_qs, 25)
        salidas_page = salidas_paginator.get_page(request.GET.get('spage') or 1)

        # 3. Solicitudes pendientes de autorización hechas por miembros de mi departamento
        solicitudes_pendientes = (
            SolicitudMaterial.objects
            .filter(estado='PENDIENTE_AUTORIZACION', usuario__perfil__departamento=departamento)
            .select_related('usuario', 'orden_trabajo', 'ubicacion_origen')
            .prefetch_related('items__material__unidad_medida')
            .distinct()
            .order_by('-fecha_solicitud')
        )
        total_pendientes = solicitudes_pendientes.count()

    context = {
        'departamento': departamento,
        'es_aprobador': es_aprobador,
        'materiales_top': materiales_top if departamento else [],
        'salidas_page': salidas_page if departamento else None,
        'solicitudes_pendientes': solicitudes_pendientes,
        'q': q,
        'total_materiales': total_materiales if departamento else 0,
        'total_salidas': total_salidas,
        'total_pendientes': total_pendientes,
        'title': 'Dashboard de mi Departamento',
    }
    return render(request, 'inventarios/dashboard_departamento.html', context)


@login_required
@require_POST
def solicitud_aprobar_departamento(request, pk):
    """
    Aprueba o rechaza una solicitud desde el dashboard de departamento.
    Requiere login y que el usuario sea aprobador de salidas de su departamento,
    y que la solicitud incluya materiales de ese departamento.
    """
    from django.utils import timezone
    from .models import SolicitudMaterial

    perfil = getattr(request.user, 'perfil', None)
    departamento = getattr(perfil, 'departamento', None)
    es_aprobador = bool(perfil and getattr(perfil, 'aprobador_salidas', False))

    if not departamento or not es_aprobador:
        return JsonResponse({'status': 'error', 'message': 'No tienes permisos de aprobador en tu departamento.'}, status=403)

    solicitud = get_object_or_404(SolicitudMaterial, pk=pk)

    # Validar que el solicitante pertenezca al departamento del aprobador
    sol_perfil = getattr(solicitud.usuario, 'perfil', None)
    sol_departamento = getattr(sol_perfil, 'departamento', None)
    if sol_departamento_id := getattr(sol_departamento, 'id', None):
        if sol_departamento_id != departamento.id:
            return JsonResponse({'status': 'error', 'message': 'Esta solicitud no pertenece a tu departamento.'}, status=403)
    else:
        return JsonResponse({'status': 'error', 'message': 'Esta solicitud no pertenece a tu departamento.'}, status=403)

    if solicitud.estado != 'PENDIENTE_AUTORIZACION':
        return JsonResponse({'status': 'error', 'message': f'La solicitud ya no está pendiente (estado: {solicitud.get_estado_display()}).'}, status=400)

    accion = (request.POST.get('accion') or '').lower()

    if accion == 'aprobar':
        solicitud.estado = 'PENDIENTE'
        solicitud.autorizado_por = request.user
        solicitud.fecha_autorizacion = timezone.now()
        solicitud.save(update_fields=['estado', 'autorizado_por', 'fecha_autorizacion'])
        try:
            from .utils_ntfy import notificar_nueva_solicitud
            notificar_nueva_solicitud(solicitud)
        except Exception:
            pass
        try:
            from .utils_n8n import notify_powerautomate_almacen
            notify_powerautomate_almacen(solicitud)
        except Exception:
            pass
        try:
            from .utils_push import push_a_almacen
            push_a_almacen(solicitud)
        except Exception:
            pass
        return JsonResponse({'status': 'success', 'message': 'Solicitud autorizada.', 'nuevo_estado': 'PENDIENTE'})
    elif accion == 'rechazar':
        solicitud.estado = 'RECHAZADO'
        solicitud.rechazado_por = request.user
        solicitud.fecha_rechazo = timezone.now()
        solicitud.save(update_fields=['estado', 'rechazado_por', 'fecha_rechazo'])
        return JsonResponse({'status': 'success', 'message': 'Solicitud rechazada.', 'nuevo_estado': 'RECHAZADO'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Acción no válida.'}, status=400)


@login_required
def solicitud_detalle_departamento(request, pk):
    """
    Detalle de una solicitud accesible desde el dashboard de departamento.
    Permite ver la solicitud si el usuario es el dueño, o si pertenece al mismo
    departamento que el solicitante (para que el equipo/aprobador pueda verla).
    """
    from .models import SolicitudMaterial

    pedido = get_object_or_404(SolicitudMaterial, pk=pk)

    perfil = getattr(request.user, 'perfil', None)
    mi_departamento_id = getattr(getattr(perfil, 'departamento', None), 'id', None)

    sol_perfil = getattr(pedido.usuario, 'perfil', None)
    sol_departamento_id = getattr(getattr(sol_perfil, 'departamento', None), 'id', None)

    es_dueno = pedido.usuario_id == request.user.id
    mismo_departamento = bool(mi_departamento_id and mi_departamento_id == sol_departamento_id)
    # Los aprobadores de salidas (p. ej. personal de Almacenes) también pueden ver el detalle
    es_aprobador = bool(perfil and getattr(perfil, 'aprobador_salidas', False))

    if not (es_dueno or mismo_departamento or es_aprobador or request.user.is_superuser):
        return HttpResponse("No tienes permiso para ver esta solicitud.", status=403)

    items = pedido.items.select_related('material', 'material__unidad_medida').all()
    for item in items:
        m = item.material
        item.image_url = m.imagen.url if m.imagen else ''

    # El personal del grupo "Almacenes" puede despachar/confirmar entrega
    es_almacen = request.user.groups.filter(name__iexact='Almacenes').exists()
    puede_despachar = es_almacen and pedido.estado == 'PENDIENTE'
    puede_confirmar_entrega = es_almacen and pedido.estado == 'LISTO_RECOLECCION'

    # Personas autorizadas para aprobar los materiales de esta solicitud
    # (misma lógica que el webhook de autorización).
    try:
        from .utils_n8n import _obtener_aprobadores_solicitud
        sol_perfil_obj = getattr(pedido.usuario, 'perfil', None)
        jefe_directo = getattr(sol_perfil_obj, 'responsable', None) if sol_perfil_obj else None
        jefe_departamento = None
        if sol_perfil_obj and getattr(sol_perfil_obj, 'departamento', None):
            jefe_departamento = getattr(sol_perfil_obj.departamento, 'responsable', None)
        superior = jefe_directo or jefe_departamento
        aprobadores = _obtener_aprobadores_solicitud(pedido, superior)
    except Exception:
        aprobadores = []

    return render(request, 'inventarios/mobile_detalle_pedido.html', {
        'pedido': pedido,
        'items': items,
        'puede_despachar': puede_despachar,
        'puede_confirmar_entrega': puede_confirmar_entrega,
        'es_almacen': es_almacen,
        'aprobadores': aprobadores,
    })


@login_required
@require_POST
def solicitud_despachar(request, pk):
    """
    Despacha (liquida) los materiales de una solicitud. Solo para usuarios del
    grupo 'Almacenes'. Liquida cada MovimientoInventario (descuenta stock) y marca
    la solicitud como ENTREGADO.
    """
    from django.utils import timezone
    from .models import SolicitudMaterial

    if not request.user.groups.filter(name__iexact='Almacenes').exists():
        return JsonResponse({'status': 'error', 'message': 'Solo el personal de Almacenes puede despachar.'}, status=403)

    solicitud = get_object_or_404(SolicitudMaterial, pk=pk)

    if solicitud.estado != 'PENDIENTE':
        return JsonResponse({'status': 'error', 'message': f'La solicitud no está lista para despacho (estado: {solicitud.get_estado_display()}).'}, status=400)

    try:
        # El despacho NO descuenta stock todavía. Marca la orden como lista para
        # recolección y notifica al solicitante. El stock se descuenta al confirmar la entrega.
        solicitud.estado = 'LISTO_RECOLECCION'
        solicitud.entregado_por = request.user  # quien preparó/despachó
        solicitud.save(update_fields=['estado', 'entregado_por'])

        # Notificar al solicitante que su orden está lista para recolección
        try:
            from .utils_n8n import notify_powerautomate_recoleccion
            notify_powerautomate_recoleccion(solicitud)
        except Exception:
            pass

        return JsonResponse({'status': 'success', 'message': f'Solicitud #{solicitud.id} despachada. Se notificó al solicitante que está lista para recolección.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error al despachar: {str(e)}'}, status=500)


@login_required
@require_POST
def solicitud_confirmar_entrega(request, pk):
    """
    Confirma la entrega de una solicitud que está lista para recolección.
    Solo para el grupo 'Almacenes'. Aquí se liquida el stock y la solicitud
    pasa a ENTREGADO.
    """
    from django.utils import timezone
    from .models import SolicitudMaterial

    if not request.user.groups.filter(name__iexact='Almacenes').exists():
        return JsonResponse({'status': 'error', 'message': 'Solo el personal de Almacenes puede confirmar la entrega.'}, status=403)

    solicitud = get_object_or_404(SolicitudMaterial, pk=pk)

    if solicitud.estado != 'LISTO_RECOLECCION':
        return JsonResponse({'status': 'error', 'message': f'La solicitud no está lista para recolección (estado: {solicitud.get_estado_display()}).'}, status=400)

    try:
        with transaction.atomic():
            # Liquidar cada movimiento (aprueba y descuenta stock)
            for mov in solicitud.items.all():
                if mov.estado != 'APROBADO':
                    mov.liquidar(request.user)

            solicitud.estado = 'ENTREGADO'
            if not solicitud.entregado_por:
                solicitud.entregado_por = request.user
            solicitud.fecha_entrega = timezone.now()
            solicitud.save(update_fields=['estado', 'entregado_por', 'fecha_entrega'])

        # Notificar despacho/entrega (Power Automate) - no bloquear si falla
        try:
            from .utils_n8n import notify_powerautomate_despacho
            notify_powerautomate_despacho(solicitud)
        except Exception:
            pass

        return JsonResponse({'status': 'success', 'message': f'Entrega de la solicitud #{solicitud.id} confirmada. Stock actualizado.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error al confirmar entrega: {str(e)}'}, status=500)
