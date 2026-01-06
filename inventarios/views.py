from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from .models import Material, StockRecord, MovimientoInventario
from mantenimiento.models import OrdenTrabajo
from activos.models import Ubicacion

@login_required
def registrar_salida_view(request):
    """
    Interfaz visual premium para registrar salidas de inventario.
    """
    materiales = Material.objects.all().prefetch_related('existencias', 'existencias__ubicacion')
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
