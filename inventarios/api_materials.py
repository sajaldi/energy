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
        # Determine image URL (using a placeholder if not available)
        # Since Material model doesn't have an image field yet, use a default icon
        # You can replace this with a static file path or add an image field to Material model
        image_url = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 24 24' fill='none' stroke='%2310b981' stroke-width='1.5'%3E%3Cpath d='M20 7h-4V4c0-1.1-.9-2-2-2h-4c-1.1 0-2 .9-2 2v3H4c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2zM10 4h4v3h-4V4zm10 16H4V9h16v11z'/%3E%3Cpath d='M12 12h-1v4h1v-4zm0 5h-1v1h1v-1z'/%3E%3C/svg%3E"
        # If you have an image field, replace with: image_url = m.imagen.url if m.imagen else default_url
        
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
    categories = CategoriaMaterial.objects.all().order_by('nombre')
    data = [{'id': c.id, 'nombre': c.nombre} for c in categories]
    return JsonResponse({'results': data})
