from decimal import Decimal
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from .models import Modelo, Marca, Categoria, CaracteristicaCategoria, ValorCaracteristicaModelo
from core.models import UnidadMedida
from django.db.models import Count, Q
import json

@staff_member_required
def modelos_dashboard(request):
    """Dashboard para gestionar los modelos de activos"""
    search = request.GET.get('search', '').strip()
    marca_id = request.GET.get('marca')
    categoria_id = request.GET.get('categoria')
    letra = request.GET.get('letra', '').upper()
    
    queryset = Modelo.objects.select_related('marca', 'categoria').annotate(
        total_activos=Count('activos')
    ).order_by('marca__nombre', 'nombre')
    
    if search:
        queryset = queryset.filter(Q(nombre__icontains=search) | Q(descripcion__icontains=search))
    
    if marca_id:
        queryset = queryset.filter(marca_id=marca_id)
        
    if categoria_id:
        queryset = queryset.filter(categoria_id=categoria_id)

    if letra and len(letra) == 1:
        queryset = queryset.filter(marca__nombre__istartswith=letra)
        
    from django.core.paginator import Paginator
    from collections import defaultdict

    # Obtener todas las marcas únicas en el queryset filtrado (para el índice rápido completo)
    marcas_en_filtro = Marca.objects.filter(modelos__in=queryset).distinct().order_by('nombre')

    # Paginación
    items_per_page = 24
    paginator = Paginator(queryset, items_per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Agrupar solo los modelos de la página actual
    modelos_por_marca = defaultdict(list)
    for m in page_obj:
        modelos_por_marca[m.marca].append(m)
    
    # Ordenar marcas alfabéticamente para la página actual
    modelos_por_marca = dict(sorted(modelos_por_marca.items(), key=lambda x: x[0].nombre))

    # Datos para filtros y modales
    marcas = Marca.objects.all().order_by('nombre')
    categorias = Categoria.objects.all().order_by('nombre')
    unidades = UnidadMedida.objects.all().order_by('nombre')
    
    return render(request, 'activos/modelos_dashboard.html', {
        'modelos_por_marca': modelos_por_marca,
        'marcas_en_filtro': marcas_en_filtro,
        'page_obj': page_obj,
        'marcas': marcas,
        'categorias': categorias,
        'unidades': unidades,
        'total_modelos': paginator.count,
        'search': search,
        'current_marca': marca_id,
        'current_cat': categoria_id,
        'current_letra': letra
    })

from django.contrib.auth.decorators import login_required

@login_required
def modelo_detail_api(request):
    """API para obtener detalles completos de un modelo (360 view)"""
    pk = request.GET.get('id', '').replace(',', '').replace('.', '')
    try:
        m = Modelo.objects.select_related('marca', 'categoria', 'unidad_medida').get(pk=pk)
        
        # Manejo seguro de la imagen
        image_url = ""
        try:
            image_url = m.imagen if m.imagen else ""
        except Exception as img_err:
            image_url = getattr(m, 'imagen_url', '') or ""

        # Obtener activos asociados
        activos = []
        for a in m.activos.select_related('ubicacion').all(): 
            ub = a.ubicacion
            activos.append({
                'id': a.id,
                'codigo': a.codigo_interno,
                'nombre': a.nombre,
                'ubicacion': ub.nombre if ub else 'Sin Ubicación',
                'ubicacion_jerarquica': ub.get_ruta_completa() if ub else 'Sin Ubicación',
                'estado': a.get_estado_display(),
                'estado_raw': a.estado
            })

        # Obtener rutinas de mantenimiento (vía categoría)
        from mantenimiento.models import Rutina
        rutinas = []
        if m.categoria:
            # Buscar rutinas vinculadas a esta categoría
            qs_rutinas = Rutina.objects.filter(categoria_activo=m.categoria).select_related('frecuencia', 'tipo')
            for r in qs_rutinas:
                rutinas.append({
                    'id': r.id,
                    'codigo': r.codigo_rutina or f"RT-{r.id}",
                    'nombre': r.nombre,
                    'frecuencia': r.frecuencia.nombre if r.frecuencia else 'N/A',
                    'tipo': r.tipo.nombre if r.tipo else 'General',
                    'tiempo': str(r.tiempo_estimado) if r.tiempo_estimado else 'N/A'
                })

        # Obtener características de la categoría y los valores del modelo
        caracteristicas = []
        if m.categoria:
            cars_cat = CaracteristicaCategoria.objects.filter(categoria=m.categoria).select_related('unidad_medida')
            valores = {v.caracteristica_id: v.valor for v in ValorCaracteristicaModelo.objects.filter(modelo=m)}
            for c in cars_cat:
                caracteristicas.append({
                    'id': c.id,
                    'nombre': c.nombre,
                    'tipo_dato': c.tipo_dato,
                    'unidad_medida': c.unidad_medida.nombre if c.unidad_medida else '',
                    'opciones': c.opciones,
                    'requerido': c.requerido,
                    'valor': valores.get(c.id, '')
                })

        # Obtener materiales compatibles
        from django.db.models import Sum, OuterRef, Subquery, DecimalField
        from django.db.models.functions import Coalesce
        from inventarios.models import StockRecord, CompatibilidadMaterial

        stock_subquery = StockRecord.objects.filter(material=OuterRef('material_id')).values('material').annotate(total=Sum('cantidad')).values('total')
        
        repuestos = CompatibilidadMaterial.objects.filter(modelo=m).select_related(
            'material__unidad_medida', 'material__marca'
        ).annotate(
            stock_actual=Coalesce(Subquery(stock_subquery, output_field=DecimalField()), Decimal('0.00'))
        )

        materiales = []
        for comp in repuestos:
            mat = comp.material
            materiales.append({
                'material_id': mat.id,
                'nombre': mat.nombre,
                'sku': mat.sku,
                'descripcion': mat.descripcion or '',
                'tipo_material': mat.get_tipo_material_display() if hasattr(mat, 'get_tipo_material_display') else mat.tipo_material,
                'stock': float(comp.stock_actual),
                'marca': mat.marca.nombre if mat.marca else 'S/M',
                'imagen': mat.imagen.url if mat.imagen else '',
                'cantidad_sugerida': float(comp.cantidad_sugerida),
                'unidad_abreviatura': mat.unidad_medida.abreviatura if mat.unidad_medida else '',
                'notas': comp.notas or ''
            })

        return JsonResponse({
            'status': 'success',
            'modelo': {
                'id': m.id,
                'nombre': m.nombre,
                'marca_nombre': m.marca.nombre,
                'marca_id': m.marca_id,
                'categoria_nombre': m.categoria.nombre if m.categoria else "Sin Categoría",
                'categoria_id': m.categoria_id or "",
                'unidad_medida_id': m.unidad_medida_id or "",
                'unidad_medida_nombre': m.unidad_medida.nombre if m.unidad_medida else "N/A",
                'precio_promedio': float(m.precio_promedio or 0),
                'descripcion': m.descripcion or "",
                'imagen_url': getattr(m, 'imagen_url', '') or "",
                'image_display_url': image_url,
                'total_activos': m.activos.count()
            },
            'activos': activos,
            'rutinas': rutinas,
            'caracteristicas': caracteristicas,
            'materiales': materiales
        })
    except Modelo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': f'Modelo ID {pk} no encontrado'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def modelo_save_api(request):
    """API para crear o actualizar un modelo"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        # Nota: Si hay archivos, request.POST + request.FILES. 
        # Si es JSON puro, json.loads(request.body)
        
        pk = request.POST.get('id')
        nombre = request.POST.get('nombre')
        marca_id = request.POST.get('marca_id')
        
        if not nombre or not marca_id:
            return JsonResponse({'status': 'error', 'message': 'Nombre y Marca son obligatorios'}, status=400)
            
        if pk:
            m = Modelo.objects.get(pk=pk)
        else:
            m = Modelo()
            
        m.nombre = nombre
        m.marca_id = marca_id
        m.categoria_id = request.POST.get('categoria_id') or None
        m.unidad_medida_id = request.POST.get('unidad_medida_id') or None
        m.precio_promedio = request.POST.get('precio_promedio') or 0
        m.descripcion = request.POST.get('descripcion') or ""
        m.imagen_url = request.POST.get('imagen_url') or ""
        
        if 'imagen_archivo' in request.FILES:
            m.imagen_archivo = request.FILES['imagen_archivo']
            
        m.save()
        
        # Guardar características
        if m.categoria_id:
            cars_cat = CaracteristicaCategoria.objects.filter(categoria_id=m.categoria_id)
            for c in cars_cat:
                key = f'char_{c.id}'
                if key in request.POST:
                    val = request.POST.get(key)
                    ValorCaracteristicaModelo.objects.update_or_create(
                        modelo=m,
                        caracteristica=c,
                        defaults={'valor': val}
                    )

        # Guardar Materiales Compatibles
        material_ids = request.POST.getlist('material_ids[]')
        # Limpiar compatibilidades anteriores que ya no están en la lista
        from inventarios.models import CompatibilidadMaterial
        CompatibilidadMaterial.objects.filter(modelo=m).exclude(material_id__in=material_ids).delete()
        
        # Agregar/Actualizar las actuales
        for mat_id in material_ids:
            qty = request.POST.get(f'mat_qty_{mat_id}', 1)
            CompatibilidadMaterial.objects.update_or_create(
                modelo=m,
                material_id=mat_id,
                defaults={'cantidad_sugerida': qty}
            )
        
        return JsonResponse({'status': 'success', 'message': 'Modelo guardado correctamente'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def modelo_delete_api(request, pk):
    """API para eliminar un modelo"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        m = Modelo.objects.get(pk=pk)
        if m.activos.exists():
            return JsonResponse({'status': 'error', 'message': 'No se puede eliminar un modelo con activos asociados'}, status=400)
            
        m.delete()
        return JsonResponse({'status': 'success', 'message': 'Modelo eliminado'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def categoria_caracteristicas_api(request):
    """API para obtener las características de una categoría específica (para el modal de edición)"""
    cat_id = request.GET.get('categoria_id')
    if not cat_id:
        return JsonResponse({'status': 'success', 'caracteristicas': []})
        
    try:
        cars = CaracteristicaCategoria.objects.filter(categoria_id=cat_id).select_related('unidad_medida')
        caracteristicas = []
        for c in cars:
            caracteristicas.append({
                'id': c.id,
                'nombre': c.nombre,
                'tipo_dato': c.tipo_dato,
                'unidad_medida': c.unidad_medida.nombre if c.unidad_medida else '',
                'opciones': c.opciones,
                'requerido': c.requerido,
            })
        return JsonResponse({'status': 'success', 'caracteristicas': caracteristicas})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
