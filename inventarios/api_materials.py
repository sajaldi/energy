from decimal import Decimal
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from inventarios.models import Material, CategoriaMaterial, StockRecord

@login_required
def api_list_materials(request):
    """
    API endpoint to list materials with pagination and filtering.
    For use in visual selector modal.
    """
    query = request.GET.get('q', '')
    category_id = request.GET.get('category')
    ubicacion_id = request.GET.get('ubicacion')
    page_number = request.GET.get('page', 1)
    
    from django.db.models import Sum, Q, OuterRef, Subquery, DecimalField
    from django.db.models.functions import Coalesce

    # Optimizamos: En lugar de annotate global con Sum (que puede duplicar filas si hay muchos joins),
    # usamos una Subquery para calcular el stock por material de forma aislada.
    
    stock_subquery = StockRecord.objects.filter(material=OuterRef('pk'))
    if ubicacion_id:
        stock_subquery = stock_subquery.filter(ubicacion_id=ubicacion_id)
    
    stock_total_expr = Subquery(
        stock_subquery.values('material').annotate(total=Sum('cantidad')).values('total'),
        output_field=DecimalField()
    )

    materials = Material.objects.select_related('categoria', 'unidad_medida').prefetch_related('departamentos', 'existencias__ubicacion').annotate(
        stock_total=Coalesce(stock_total_expr, Decimal('0.00'))
    ).order_by('nombre')

    if query:
        materials = materials.filter(
            Q(nombre__icontains=query) | 
            Q(sku__icontains=query) |
            Q(descripcion__icontains=query)
        )
        
    if category_id:
        materials = materials.filter(categoria_id=category_id)

    # Comentamos el filtro restrictivo de stock para permitir ver catálogo
    # if ubicacion_id:
    #     materials = materials.filter(stock_total__gt=0)
        
    paginator = Paginator(materials, 30) # Aumentamos a 30 para mejor grid
    page_obj = paginator.get_page(page_number)
    
    data = []
    
    user_depto_id = None
    if hasattr(request.user, 'perfil') and request.user.perfil.departamento_id:
        user_depto_id = request.user.perfil.departamento_id
        
    for m in page_obj:
        if hasattr(m, 'imagen') and m.imagen:
             image_url = m.imagen.url
        else:
             # SVG de una cajita de inventario
             image_url = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 24 24' fill='none' stroke='%233b82f6' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z'%3E%3C/path%3E%3Cpolyline points='3.27 6.96 12 12.01 20.73 6.96'%3E%3C/polyline%3E%3Cline x1='12' y1='22.08' x2='12' y2='12'%3E%3C/line%3E%3C/svg%3E"

        # Lógica de restricción por departamento
        dept_ids = [d.id for d in m.departamentos.all()]
        if not dept_ids:
            is_allowed = True # Global
        elif user_depto_id and user_depto_id in dept_ids:
            is_allowed = True
        else:
            is_allowed = False

        # Obtener bodegas con stock
        bodegas_list = []
        for ex in m.existencias.all():
            if ex.cantidad > 0:
                bodegas_list.append(ex.ubicacion.nombre)
        
        unique_bodegas = sorted(list(set(bodegas_list)))

        data.append({
            'id': m.id,
            'nombre': m.nombre,
            'sku': m.sku,
            'descripcion': m.descripcion or '',
            'unidad': m.unidad_medida.nombre if m.unidad_medida else 'Unidad',
            'precio_estimado': float(m.precio_estimado),
            'stock': float(m.stock_total or 0),
            'categoria': m.categoria.nombre if m.categoria else 'General',
            'tipo_material': m.get_tipo_material_display() if hasattr(m, 'get_tipo_material_display') else m.tipo_material,
            'image_url': image_url,
            'is_allowed': is_allowed,
            'bodegas': unique_bodegas
        })
        
    return JsonResponse({
        'results': data,
        'has_next': page_obj.has_next(),
        'num_pages': paginator.num_pages,
        'current_page': page_obj.number
    })

@login_required
def api_list_categories(request):
    categories = list(CategoriaMaterial.objects.all().order_by('nombre'))
    
    def build_tree(parent_id):
        nodes = []
        for cat in categories:
            if cat.padre_id == parent_id:
                children = build_tree(cat.id)
                nodes.append({
                    'id': cat.id,
                    'nombre': cat.nombre,
                    'children': children
                })
        return nodes

    tree = build_tree(None)
    return JsonResponse({'results': tree})

@login_required
def api_master_sync(request):
    """
    Consolidates ALL necessary data for offline mode (Basement Mode).
    Returns materials, categories, units, and warehouse locations.
    """
    from activos.models import Ubicacion
    from .models import UnidadMedida, StockRecord
    from django.db.models import Sum, OuterRef, Subquery, DecimalField
    from django.db.models.functions import Coalesce
    from decimal import Decimal

    # 1. Materials with stock
    stock_subquery = StockRecord.objects.filter(material=OuterRef('pk'))
    stock_total_expr = Subquery(
        stock_subquery.values('material').annotate(total=Sum('cantidad')).values('total'),
        output_field=DecimalField()
    )

    materials_qs = Material.objects.select_related('categoria', 'unidad_medida').annotate(
        stock_total=Coalesce(stock_total_expr, Decimal('0.00'))
    ).order_by('nombre')

    # Filtrado por departamento si aplica
    user_depto_id = None
    if hasattr(request.user, 'perfil') and request.user.perfil.departamento_id:
        user_depto_id = request.user.perfil.departamento_id

    materials_data = []
    for m in materials_qs:
        # Lógica de restricción básica
        dept_ids = [d.id for d in m.departamentos.all()]
        if dept_ids and user_depto_id and user_depto_id not in dept_ids:
            continue

        materials_data.append({
            'id': m.id,
            'nombre': m.nombre,
            'sku': m.sku,
            'desc': m.descripcion or '',
            'cat_id': m.categoria_id,
            'uni': m.unidad_medida.abreviatura if m.unidad_medida else 'UND',
            'stock': float(m.stock_total or 0)
        })

    # 2. Categories
    categories = list(CategoriaMaterial.objects.values('id', 'nombre', 'padre_id'))

    # 3. Units
    units = list(UnidadMedida.objects.values('id', 'nombre', 'abreviatura'))

    # 4. Locations (Warehouse only)
    locations = list(Ubicacion.objects.filter(tipo='ALMACEN').values('id', 'nombre'))

    return JsonResponse({
        'status': 'success',
        'materials': materials_data,
        'categories': categories,
        'units': units,
        'locations': locations,
        'timestamp': timezone.now().isoformat() if 'timezone' in globals() else None
    })
