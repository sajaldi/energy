from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from .models import Material, StockRecord, MovimientoInventario
from mantenimiento.models import OrdenTrabajo
from activos.models import Ubicacion, Categoria
from .cart_utils import Cart
import json

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
    ordenes_activas = OrdenTrabajo.objects.filter(estado__in=['PROGRAMADA', 'EJECUCION']).select_related('ubicacion')
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
                return redirect('registrar_salida')

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
        'ordenes_activas': ordenes_activas,
        'ubicaciones': ubicaciones,
        'categorias': categorias,
        'cat_id': int(cat_id) if cat_id else None,
    }
    return render(request, 'inventarios/registrar_salida.html', context)

@login_required
def api_get_material_stock(request, material_id):
    """
    Retorna los niveles de stock por ubicación para un material dado.
    """
    material = get_object_or_404(Material, id=material_id)
    existencias = material.existencias.select_related('ubicacion').values(
        'ubicacion_id', 'ubicacion__nombre', 'cantidad'
    )
    return JsonResponse({
        'material': material.nombre,
        'unidad': material.unidad_medida,
        'existencias': list(existencias)
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
    ordenes_activas = OrdenTrabajo.objects.filter(estado__in=['PROGRAMADA', 'EJECUCION'])
    
    return render(request, 'inventarios/detalle_carrito.html', {
        'items': items,
        'ubicaciones': ubicaciones,
        'ordenes_activas': ordenes_activas,
        'cart_count': len(cart)
    })

@login_required
def cart_checkout(request):
    """Procesa el carrito y crea los movimientos de inventario."""
    if request.method == 'POST':
        cart = Cart(request)
        items = cart.get_items()
        
        ubicacion_id = request.POST.get('ubicacion_origen')
        ot_id = request.POST.get('orden_trabajo')
        comentarios = request.POST.get('comentarios', '')
        
        if not items:
            messages.error(request, "El carrito está vacío.")
            return redirect('cart_detail')
            
        if not ubicacion_id:
            messages.error(request, "Debes seleccionar una ubicación de origen.")
            return redirect('cart_detail')

        try:
            ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
            ot = OrdenTrabajo.objects.filter(id=ot_id).first() if ot_id else None
            
            # Validar stock para todos los items
            for item in items:
                material = item['material']
                qty = Decimal(str(item['quantity']))
                stock_record = StockRecord.objects.filter(material=material, ubicacion=ubicacion).first()
                available = stock_record.cantidad if stock_record else 0
                if available < qty:
                    raise ValueError(f"Stock insuficiente para {material.nombre}. Disponible: {available}")

            # Crear movimientos
            for item in items:
                MovimientoInventario.objects.create(
                    material=item['material'],
                    tipo='SALIDA',
                    cantidad=Decimal(str(item['quantity'])),
                    ubicacion_origen=ubicacion,
                    orden_trabajo=ot,
                    usuario=request.user,
                    comentarios=comentarios
                )
            
            cart.clear()
            messages.success(request, f"Se han registrado {len(items)} solicitudes de salida correctamente.")
            return redirect('registrar_salida')
            
        except Exception as e:
            messages.error(request, f"Error en checkout: {str(e)}")
            return redirect('cart_detail')
            
    return redirect('cart_detail')
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
