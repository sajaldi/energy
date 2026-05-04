from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from .models import Modelo, Marca, Categoria
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
    """API para obtener detalles de un modelo"""
    pk = request.GET.get('id', '').replace(',', '').replace('.', '')
    try:
        m = Modelo.objects.select_related('marca', 'categoria', 'unidad_medida').get(pk=pk)
        
        # Manejo seguro de la imagen
        image_url = ""
        try:
            image_url = m.imagen if m.imagen else ""
        except Exception as img_err:
            image_url = getattr(m, 'imagen_url', '') or ""

        return JsonResponse({
            'status': 'success',
            'modelo': {
                'id': m.id,
                'nombre': m.nombre,
                'marca_id': m.marca_id,
                'categoria_id': m.categoria_id or "",
                'unidad_medida_id': m.unidad_medida_id or "",
                'precio_promedio': float(m.precio_promedio or 0),
                'descripcion': m.descripcion or "",
                'imagen_url': getattr(m, 'imagen_url', '') or "",
                'image_display_url': image_url
            }
        })
    except Modelo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': f'Modelo ID {pk} no encontrado'}, status=404)
    except Exception as e:
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
