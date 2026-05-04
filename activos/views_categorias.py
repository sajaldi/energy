from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from .models.categoria import Categoria
from django.db.models import Count, Q
import json

def build_categoria_tree(all_categories, search=None):
    """
    Construye el árbol jerárquico de categorías en memoria.
    """
    # 1. Mapear categorías por padre
    hijos_por_padre = {}
    for cat in all_categories:
        padre_id = cat.padre_id
        if padre_id not in hijos_por_padre:
            hijos_por_padre[padre_id] = []
        hijos_por_padre[padre_id].append(cat)

    # 2. Función recursiva para construir nodos
    def construct_node(cat):
        sub_categories = hijos_por_padre.get(cat.id, [])
        
        sub_tree = []
        for sub_cat in sub_categories:
            node = construct_node(sub_cat)
            if node:
                sub_tree.append(node)

        # Si hay búsqueda, solo mostramos si coincide el nombre o tiene hijos que coinciden
        if search:
            s = search.lower()
            if s in cat.nombre.lower() or sub_tree:
                return {
                    'categoria': cat,
                    'subcategorias': sub_tree,
                }
            return None
        
        return {
            'categoria': cat,
            'subcategorias': sub_tree,
        }

    # 3. Iniciar desde las raíces
    final_tree = []
    raices = hijos_por_padre.get(None, [])
    for root_cat in raices:
        node = construct_node(root_cat)
        if node:
            final_tree.append(node)
            
    return final_tree

@staff_member_required
def categorias_dashboard(request):
    """Dashboard para gestionar las categorías de activos"""
    search = request.GET.get('search', '').strip()
    
    # Carga masiva
    all_categories = list(Categoria.objects.all().order_by('nombre'))
    
    # Árbol
    tree = build_categoria_tree(all_categories, search)
    
    # Datos para modales
    todas_categorias = Categoria.objects.all().order_by('nombre')
    total_categorias = Categoria.objects.count()
    
    return render(request, 'activos/categorias_dashboard.html', {
        'tree': tree,
        'todas_categorias': todas_categorias,
        'total_categorias': total_categorias,
        'search': search
    })

@staff_member_required
def categoria_detail_api(request, pk):
    """API para obtener detalles de una categoría"""
    try:
        cat = Categoria.objects.get(pk=pk)
        return JsonResponse({
            'status': 'success',
            'categoria': {
                'id': cat.id,
                'nombre': cat.nombre,
                'padre_id': cat.padre_id or "",
                'icono': cat.icono or "location",
                'descripcion': cat.descripcion or ""
            }
        })
    except Categoria.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Categoría no encontrada'}, status=404)

@staff_member_required
def categoria_save_api(request):
    """API para crear o actualizar una categoría"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        data = json.loads(request.body)
        pk = data.get('id')
        nombre = data.get('nombre')
        
        if not nombre:
            return JsonResponse({'status': 'error', 'message': 'El nombre es obligatorio'}, status=400)
            
        if pk:
            cat = Categoria.objects.get(pk=pk)
        else:
            cat = Categoria()
            
        cat.nombre = nombre
        cat.icono = data.get('icono') or "location"
        cat.descripcion = data.get('descripcion') or ""
        
        padre_id = data.get('padre_id')
        if padre_id:
            if str(padre_id) == str(pk):
                return JsonResponse({'status': 'error', 'message': 'Una categoría no puede ser padre de sí misma'}, status=400)
            cat.padre = Categoria.objects.get(pk=padre_id)
        else:
            cat.padre = None
            
        cat.save()
        return JsonResponse({'status': 'success', 'message': 'Categoría guardada correctamente'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def categoria_delete_api(request, pk):
    """API para eliminar una categoría"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        cat = Categoria.objects.get(pk=pk)
        if cat.subcategorias.exists():
            return JsonResponse({'status': 'error', 'message': 'No se puede eliminar una categoría con subcategorías'}, status=400)
            
        # Comprobar si hay activos asociados (requiere importación de Activo)
        from .models.activo import Activo
        if Activo.objects.filter(modelo__categoria=cat).exists():
            return JsonResponse({'status': 'error', 'message': 'No se puede eliminar una categoría con activos asociados'}, status=400)
            
        cat.delete()
        return JsonResponse({'status': 'success', 'message': 'Categoría eliminada'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def get_categoria_modelos_api(request, pk):
    """API para obtener los modelos relacionados a una categoría"""
    try:
        cat = Categoria.objects.get(pk=pk)
        # Incluir modelos de subcategorías si el usuario lo desea (por ahora solo esta)
        modelos = cat.modelos.select_related('marca').all()
        
        data = []
        for m in modelos:
            data.append({
                'id': m.id,
                'nombre': m.nombre,
                'marca': m.marca.nombre,
                'imagen': m.imagen,
                'total_activos': m.activos.count()
            })
            
        return JsonResponse({
            'status': 'success',
            'modelos': data,
            'categoria_nombre': cat.nombre
        })
    except Categoria.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Categoría no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def get_modelo_details_api(request, pk):
    """API para obtener detalles de un modelo y sus activos"""
    try:
        from .models.activo import Modelo, Activo
        m = Modelo.objects.select_related('marca', 'categoria').get(pk=pk)
        
        activos = m.activos.select_related('ubicacion').all()
        
        activos_data = []
        for a in activos:
            activos_data.append({
                'id': a.id,
                'nombre': a.nombre,
                'codigo': a.codigo_interno,
                'serie': a.serie or "S/N",
                'estado': a.get_estado_display(),
                'estado_raw': a.estado,
                'ubicacion': a.ubicacion.ruta_completa if a.ubicacion else "Sin ubicación"
            })
            
        return JsonResponse({
            'status': 'success',
            'modelo': {
                'id': m.id,
                'nombre': m.nombre,
                'marca': m.marca.nombre,
                'categoria': m.categoria.nombre if m.categoria else "N/A",
                'imagen': m.imagen,
                'descripcion': m.descripcion or "Sin descripción",
                'precio_promedio': float(m.precio_promedio or 0),
            },
            'activos': activos_data
        })
    except Modelo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Modelo no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
