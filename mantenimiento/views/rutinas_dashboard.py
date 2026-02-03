from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from ..models import Categoria, Rutina, Frecuencia, PuestoTrabajo
from django.db.models import Count, Q


def build_recursive_category_tree(categories_qs, frecuencia_int, puesto_int, search):
    """Construye un árbol recursivo de categorías y rutinas filtradas"""
    tree = []
    
    # Pre-cargar rutinas para estas categorías si es posible? 
    # Por ahora usaremos el QS pasado que ya debería tener prefetches
    
    for cat in categories_qs:
        # Filtrar rutinas de esta categoría específica
        rutinas_query = cat.rutinas.all()
        
        if frecuencia_int:
            rutinas_query = rutinas_query.filter(frecuencia_id=frecuencia_int)
        if puesto_int:
            rutinas_query = rutinas_query.filter(puesto_trabajo_id=puesto_int)
        if search:
            rutinas_query = rutinas_query.filter(
                Q(nombre__icontains=search) | 
                Q(codigo_rutina__icontains=search) |
                Q(descripcion__icontains=search)
            )
        
        rutinas_list = list(rutinas_query.select_related('frecuencia', 'puesto_trabajo', 'categoria'))
        
        # Obtener subcategorías recursivamente
        # Usamos prefetch_related en el modelo para subcategorias
        sub_categories = cat.subcategorias.all()
        sub_tree = build_recursive_category_tree(sub_categories, frecuencia_int, puesto_int, search)
        
        # Una categoría se incluye si:
        # 1. Tiene rutinas que coinciden con el filtro
        # 2. Tiene subcategorías que tienen rutinas que coinciden
        # 3. No hay filtros activos (mostrar todo el árbol vacío si es necesario)
        
        has_filters = frecuencia_int or puesto_int or search
        
        if rutinas_list or sub_tree or not has_filters:
            tree.append({
                'categoria': cat,
                'rutinas': rutinas_list,
                'subcategorias': sub_tree,
                'level': cat.level
            })
            
    return tree


@staff_member_required
def rutinas_dashboard(request):
    """Dashboard profesional para visualizar rutinas en formato de árbol jerárquico"""
    
    # Filtros
    frecuencia_id = request.GET.get('frecuencia')
    puesto_id = request.GET.get('puesto')
    search = request.GET.get('search', '').strip()
    
    # Convertir a int para facilitar comparación
    try:
        frecuencia_int = int(frecuencia_id) if frecuencia_id else None
    except ValueError:
        frecuencia_int = None
        
    try:
        puesto_int = int(puesto_id) if puesto_id else None
    except ValueError:
        puesto_int = None

    # Obtener categorías raíz
    # Optimizamos con prefetch_related recursivo si es posible, 
    # o simplemente confiamos en la recursión controlada
    categorias_root = Categoria.objects.filter(padre=None).prefetch_related(
        'rutinas',
        'rutinas__frecuencia',
        'rutinas__puesto_trabajo',
        'subcategorias'
    )
    
    # Construir el árbol jerárquico
    tree = build_recursive_category_tree(categorias_root, frecuencia_int, puesto_int, search)
    
    # Estadísticas
    frecuencias = Frecuencia.objects.annotate(total=Count('rutinas')).filter(total__gt=0)
    puestos = PuestoTrabajo.objects.annotate(total=Count('rutinas')).filter(total__gt=0)
    total_rutinas = Rutina.objects.count()
    
    return render(request, 'mantenimiento/rutinas_dashboard.html', {
        'tree': tree,
        'frecuencias': frecuencias,
        'puestos': puestos,
        'total_rutinas': total_rutinas,
        'frecuencia_selected': frecuencia_int,
        'puesto_selected': puesto_int,
        'search': search
    })


@staff_member_required
def rutina_detail_api(request, pk):
    """API que devuelve detalles de una rutina y su historial de ejecución"""
    from django.http import JsonResponse
    from ..models import OrdenTrabajo, CierreOrdenTrabajo
    
    try:
        rutina = Rutina.objects.select_related('frecuencia', 'puesto_trabajo', 'categoria').get(pk=pk)
        
        # Obtener historial de OTs realizadas
        # Limitamos a las últimas 10 para rendimiento
        historial_ots = OrdenTrabajo.objects.filter(
            rutina=rutina, 
            estado='REALIZADA'
        ).select_related('tecnico', 'cierre').order_by('-inicio_programado')[:10]
        
        history_data = []
        for ot in historial_ots:
            cierre = getattr(ot, 'cierre', None)
            history_data.append({
                'id': ot.id,
                'codigo': ot.codigo_de_orden or f"OT-{ot.id}",
                'fecha_programada': ot.inicio_programado.strftime('%d/%m/%Y'),
                'fecha_cierre': cierre.fecha_fin_real.strftime('%d/%m/%Y %H:%M') if cierre else "N/A",
                'tecnico': ot.tecnico.get_full_name() if ot.tecnico else "Sin asignar",
                'comentarios': cierre.comentarios if cierre else "",
                'hh': cierre.horas_hombre if cierre else 0,
            })
            
        data = {
            'status': 'success',
            'rutina': {
                'id': rutina.id,
                'codigo': rutina.codigo_rutina or "S/C",
                'nombre': rutina.nombre,
                'categoria': rutina.categoria.nombre if rutina.categoria else "General",
                'frecuencia': rutina.frecuencia.nombre if rutina.frecuencia else "S/F",
                'tiempo_estimado': str(rutina.tiempo_estimado) if rutina.tiempo_estimado else "N/A",
                'tecnicos': rutina.cantidad_tecnicos,
                'descripcion': rutina.descripcion or "Sin descripción",
                'herramientas': rutina.herramientas or "Ninguna",
                'admin_url': f"/admin/mantenimiento/rutina/{rutina.id}/change/"
            },
            'historial': history_data
        }
        return JsonResponse(data)
    except Rutina.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Rutina no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
