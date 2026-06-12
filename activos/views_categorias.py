from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from .models.categoria import Categoria
from .models.activo import Activo, Modelo
from django.db.models import Count, Q
from collections import defaultdict
import json

def _match_marca_modelo(terms, info):
    if not info or not terms:
        return False
    for term in terms:
        found = False
        for marca in info.get('marcas', []):
            if term in marca.lower():
                found = True
                break
        if not found:
            for marca_data in info.get('modelos_por_marca', {}).values():
                for modelo_name, _, _ in marca_data.get('modelos', []):
                    if term in modelo_name.lower():
                        found = True
                        break
                if found:
                    break
        if not found:
            return False
    return True

def _filter_info_by_search(info, terms):
    if not info or not terms:
        return info
    def _matches_all(nombre):
        nombre_lower = nombre.lower()
        return all(t in nombre_lower for t in terms)
    result = {'activos': info.get('activos', 0)}
    filtered_marcas = []
    filtered_modelos_por_marca = {}
    for marca in info.get('marcas', []):
        marca_match = all(t in marca.lower() for t in terms)
        modelos_data = info.get('modelos_por_marca', {}).get(marca, {})
        filtered_modelos = [
            (nom, mid, cnt) for nom, mid, cnt in modelos_data.get('modelos', [])
            if _matches_all(nom)
        ]
        if marca_match or filtered_modelos:
            filtered_marcas.append(marca)
            if marca_match:
                filtered_modelos_por_marca[marca] = modelos_data
            else:
                filtered_modelos_por_marca[marca] = {
                    'total': sum(c for _, _, c in filtered_modelos),
                    'modelos': filtered_modelos,
                }
    result['marcas'] = sorted(filtered_marcas)
    result['modelos_por_marca'] = filtered_modelos_por_marca
    return result

def build_categoria_tree(all_categories, search=None, hierarchical_info=None):
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
    def construct_node(cat, path=None):
        if path is None:
            path = []
        current_path = path + [cat.nombre]
        sub_categories = hijos_por_padre.get(cat.id, [])
        
        sub_tree = []
        for sub_cat in sub_categories:
            node = construct_node(sub_cat, current_path)
            if node:
                sub_tree.append(node)

        info = hierarchical_info.get(cat.id, {}) if hierarchical_info else {}

        # Si hay búsqueda, solo mostramos si coincide el nombre o tiene hijos que coinciden
        if search:
            terms = [t.strip().lower() for t in search.split('+')]
            cat_match = all(t in cat.nombre.lower() for t in terms)
            if not cat_match:
                info = _filter_info_by_search(info, terms)
            if cat_match or sub_tree or _match_marca_modelo(terms, info):
                total_modelos = sum(
                    len(md.get('modelos', []))
                    for md in info.get('modelos_por_marca', {}).values()
                )
                return {
                    'categoria': cat,
                    'subcategorias': sub_tree,
                    'total_activos': info.get('activos', 0),
                    'marcas': info.get('marcas', []),
                    'modelos_por_marca': info.get('modelos_por_marca', {}),
                    'total_modelos': total_modelos,
                    'path': current_path,
                }
            return None
        
        return {
            'categoria': cat,
            'subcategorias': sub_tree,
            'total_activos': info.get('activos', 0),
            'marcas': info.get('marcas', []),
            'modelos_por_marca': info.get('modelos_por_marca', {}),
            'total_modelos': info.get('total_modelos', 0),
        }

    # 3. Iniciar desde las raíces
    final_tree = []
    raices = hijos_por_padre.get(None, [])
    for root_cat in raices:
        node = construct_node(root_cat)
        if node:
            final_tree.append(node)
            
    return final_tree

def _compute_hierarchical_info(all_categories):
    """Calcula conteo jerárquico de activos, marcas y modelos por categoría."""
    direct_counts = dict(
        Activo.objects.filter(modelo__categoria__isnull=False)
        .values('modelo__categoria')
        .annotate(count=Count('id'))
        .values_list('modelo__categoria', 'count')
    )

    direct_brands = defaultdict(set)
    direct_modelos_por_marca = defaultdict(lambda: defaultdict(dict))
    for m in Modelo.objects.annotate(activos_count=Count('activos')).select_related('marca', 'categoria'):
        if m.categoria_id:
            direct_brands[m.categoria_id].add(m.marca.nombre)
            direct_modelos_por_marca[m.categoria_id][m.marca.nombre][m.id] = {
                'nombre': m.nombre, 'count': m.activos_count,
            }

    children_map = defaultdict(list)
    for c in all_categories:
        if c.padre_id:
            children_map[c.padre_id].append(c)

    hierarchical = {}

    def accumulate(cat):
        activos = direct_counts.get(cat.id, 0)
        brands = set(direct_brands.get(cat.id, []))
        modelos_por_marca = defaultdict(dict)
        for marca, modelos in direct_modelos_por_marca.get(cat.id, {}).items():
            for modelo_id, info in modelos.items():
                modelos_por_marca[marca][modelo_id] = dict(info)
        for child in children_map.get(cat.id, []):
            child_info = accumulate(child)
            activos += child_info['activos']
            brands.update(child_info['marcas'])
            for marca, modelos in child_info['modelos_por_marca'].items():
                for modelo_id, info in modelos.items():
                    if modelo_id not in modelos_por_marca[marca]:
                        modelos_por_marca[marca][modelo_id] = dict(info)
                    else:
                        modelos_por_marca[marca][modelo_id]['count'] += info['count']
        hierarchical[cat.id] = {
            'activos': activos,
            'marcas': sorted(brands),
            'modelos_por_marca': {
                m: {
                    'total': sum(v['count'] for v in ms.values()),
                    'modelos': sorted(
                        [(v['nombre'], k, v['count']) for k, v in ms.items()],
                        key=lambda x: x[0].lower()
                    ),
                }
                for m, ms in sorted(modelos_por_marca.items())
            },
            'total_modelos': sum(len(ms) for ms in modelos_por_marca.values()),
        }
        return {
            'activos': activos,
            'marcas': brands,
            'modelos_por_marca': dict(modelos_por_marca),
        }

    for cat in all_categories:
        if cat.padre_id is None:
            accumulate(cat)
    return hierarchical


@staff_member_required
def categorias_dashboard(request):
    """Dashboard para gestionar las categorías de activos"""
    search = request.GET.get('search', '').strip()
    
    # Carga masiva
    all_categories = list(Categoria.objects.all().order_by('nombre'))
    
    # Info jerárquica (activos, marcas, modelos)
    hierarchical_info = _compute_hierarchical_info(all_categories)
    
    # Árbol
    tree = build_categoria_tree(all_categories, search, hierarchical_info)
    
    # Datos para modales
    todas_categorias = Categoria.objects.all().order_by('nombre')
    total_categorias = Categoria.objects.count()
    total_activos = Activo.objects.count()
    
    return render(request, 'activos/categorias_dashboard.html', {
        'tree': tree,
        'todas_categorias': todas_categorias,
        'total_categorias': total_categorias,
        'total_activos': total_activos,
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
            
        # Comprobar si hay activos asociados
        if Activo.objects.filter(modelo__categoria=cat).exists():
            return JsonResponse({'status': 'error', 'message': 'No se puede eliminar una categoría con activos asociados'}, status=400)
            
        cat.delete()
        return JsonResponse({'status': 'success', 'message': 'Categoría eliminada'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
def categoria_move_api(request, pk):
    """API para mover una categoría debajo de otra (padre)"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        padre_id = data.get('padre_id')

        cat = Categoria.objects.get(pk=pk)

        if padre_id:
            if int(padre_id) == cat.id:
                return JsonResponse({'status': 'error', 'message': 'Una categoría no puede ser padre de sí misma'}, status=400)
            cat.padre = Categoria.objects.get(pk=padre_id)
        else:
            cat.padre = None

        cat.save(update_fields=['padre'])

        return JsonResponse({'status': 'success', 'message': 'Categoría movida correctamente'})
    except Categoria.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'La categoría no existe'}, status=404)
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
