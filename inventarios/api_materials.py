from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from inventarios.models import Material, CategoriaMaterial

@login_required
def api_list_materials(request):
    """
    API endpoint to list materials with pagination and filtering.
    For use in visual selector modal.
    """
    query = request.GET.get('q', '')
    category_id = request.GET.get('category')
    page_number = request.GET.get('page', 1)
    
    materials = Material.objects.all().order_by('nombre')
    
    if query:
        materials = materials.filter(
            Q(nombre__icontains=query) | 
            Q(sku__icontains=query) |
            Q(descripcion__icontains=query)
        )
        
    if category_id:
        materials = materials.filter(categoria_id=category_id)
        
    paginator = Paginator(materials, 12) # 12 items per page for grid
    page_obj = paginator.get_page(page_number)
    
    data = []
    for m in page_obj:
        if  hasattr(m, 'imagen') and m.imagen:
             image_url = m.imagen.url
        else:
             # SVG de una cajita de inventario
             image_url = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 24 24' fill='none' stroke='%233b82f6' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z'%3E%3C/path%3E%3Cpolyline points='3.27 6.96 12 12.01 20.73 6.96'%3E%3C/polyline%3E%3Cline x1='12' y1='22.08' x2='12' y2='12'%3E%3C/line%3E%3C/svg%3E"

        data.append({
            'id': m.id,
            'nombre': m.nombre,
            'sku': m.sku,
            'unidad': m.get_unidad_medida_display(),
            'precio_estimado': float(m.precio_estimado),
            'stock': float(m.get_stock_total()),
            'categoria': m.categoria.nombre if m.categoria else 'General',
            'image_url': image_url 
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
