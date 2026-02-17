from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from .models import Material, StockRecord, MovimientoInventario, SolicitudMaterial
from django.db import transaction
from mantenimiento.models import OrdenTrabajo
from activos.models import Ubicacion, Categoria
from .cart_utils import Cart
import json
import time
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.core.files.storage import default_storage
from celery.result import AsyncResult
from .tasks import import_materiales_task
from django.views.decorators.csrf import csrf_exempt
from .models import CategoriaMaterial

@login_required
def crear_solicitud_dashboard(request):
    """
    Dashboard premium para crear una Solicitud de Materiales con el selector 
    exacto de la Requisición.
    """
    ubicaciones = Ubicacion.objects.all()
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
    
    return JsonResponse({
        'id': material.id,
        'nombre': material.nombre,
        'sku': material.sku,
        'unidad': material.get_unidad_medida_display(),
        'stock_total': float(material.get_stock_total()),
        'existencias': [
            {
                'ubicacion': e['ubicacion__nombre'],
                'cantidad': float(e['cantidad']),
                'detalle': e['ubicacion_especifica']
            } for e in existencias
        ]
    })

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
def cart_checkout(request):
    """Procesa el carrito o una lista JSON y crea una orden de salida."""
    if request.method == 'POST':
        ajax_mode = request.POST.get('ajax_mode') == 'true'
        items_json = request.POST.get('items_json')
        
        ubicacion_id = request.POST.get('ubicacion_origen')
        ot_id = request.POST.get('orden_trabajo')
        comentarios = request.POST.get('comentarios', '')
        
        items_to_process = []
        
        if items_json:
            # Procesar desde JSON (Dashboard nuevo)
            try:
                raw_items = json.loads(items_json)
                for ri in raw_items:
                    mat = get_object_or_404(Material, id=ri['material_id'])
                    items_to_process.append({
                        'material': mat,
                        'quantity': ri['cantidad']
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
            
            with transaction.atomic():
                # Crear la cabecera de la orden
                solicitud = SolicitudMaterial.objects.create(
                    usuario=request.user,
                    orden_trabajo=ot,
                    ubicacion_origen=ubicacion,
                    comentarios_solicitud=comentarios
                )

                # Crear los movimientos asociados
                for item in items_to_process:
                    MovimientoInventario.objects.create(
                        solicitud=solicitud,
                        material=item['material'],
                        tipo='SALIDA',
                        cantidad=Decimal(str(item['quantity'])),
                        ubicacion_origen=ubicacion,
                        orden_trabajo=ot,
                        usuario=request.user,
                        comentarios=comentarios
                    )
            
            # Limpiar carrito solo si venimos de la vista de carrito
            if not items_json:
                Cart(request).clear()

            msg = f"Orden #{solicitud.id} registrada correctamente con {len(items_to_process)} ítems."
            if ajax_mode:
                return JsonResponse({'status': 'success', 'message': msg, 'solicitud_id': solicitud.id})
            
            messages.success(request, msg)
            return redirect('inventarios:crear_solicitud')
            
        except Exception as e:
            messages.error(request, f"Error en el proceso: {str(e)}")
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
    if not material:
        return JsonResponse({'status': 'error', 'message': 'Material no encontrado'}, status=404)
    
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
def mobile_lista_pedidos(request):
    """Listado móvil de solicitudes de material para el usuario actual."""
    pedidos = SolicitudMaterial.objects.filter(usuario=request.user).order_by('-fecha_solicitud')
    return render(request, 'inventarios/mobile_lista_pedidos.html', {'pedidos': pedidos})

@login_required
def mobile_detalle_pedido(request, pk):
    """Detalle móvil de una solicitud de material."""
    pedido = get_object_or_404(SolicitudMaterial, pk=pk, usuario=request.user)
    items = pedido.movimientos.select_related('material').all()
    return render(request, 'inventarios/mobile_detalle_pedido.html', {
        'pedido': pedido,
        'items': items
    })

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
                'unidad': material.get_unidad_medida_display(),
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
