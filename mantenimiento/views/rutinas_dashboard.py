from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from ..models import Categoria, Rutina, Frecuencia, PuestoTrabajo, Procedimiento, PasoProcedimiento
from django.db.models import Count, Q


def build_in_memory_tree(all_categories, all_rutinas, frecuencia_int, puesto_int, search):
    """
    Construye el árbol jerárquico totalmente en memoria sin consultas adicionales.
    """
    # 1. Agrupar rutinas por categoría
    rutinas_por_cat = {}
    for r in all_rutinas:
        # Aplicamos filtros de rutina aquí (o venían pre-filtrados)
        if frecuencia_int and r.frecuencia_id != frecuencia_int: continue
        if puesto_int and r.puesto_trabajo_id != puesto_int: continue
        if search:
            s = search.lower()
            if not (s in r.nombre.lower() or (r.codigo_rutina and s in r.codigo_rutina.lower()) or (r.descripcion and s in r.descripcion.lower())):
                continue
        
        if r.categoria_id not in rutinas_por_cat:
            rutinas_por_cat[r.categoria_id] = []
        rutinas_por_cat[r.categoria_id].append(r)

    # 2. Mapear categorías por padre
    hijos_por_padre = {}
    for cat in all_categories:
        padre_id = cat.padre_id
        if padre_id not in hijos_por_padre:
            hijos_por_padre[padre_id] = []
        hijos_por_padre[padre_id].append(cat)

    # 3. Función recursiva interna para construir nodos
    def construct_node(cat):
        sub_categories = hijos_por_padre.get(cat.id, [])
        rutinas_list = rutinas_por_cat.get(cat.id, [])
        
        sub_tree = []
        for sub_cat in sub_categories:
            node = construct_node(sub_cat)
            if node:
                sub_tree.append(node)

        has_filters = frecuencia_int or puesto_int or search
        # Se incluye la categoría si tiene rutinas, o subcategorías con contenido, o si no hay filtros
        if rutinas_list or sub_tree or not has_filters:
            return {
                'categoria': cat,
                'rutinas': rutinas_list,
                'subcategorias': sub_tree,
                'level': cat.level
            }
        return None

    # 4. Iniciar desde las raíces
    final_tree = []
    raices = hijos_por_padre.get(None, [])
    for root_cat in raices:
        node = construct_node(root_cat)
        if node:
            final_tree.append(node)
            
    return final_tree


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

    # --- OPTIMIZACIÓN: Carga masiva en memoria ---
    # Cargamos todas las categorías y rutinas de UNA vez para evitar N+1
    all_categories = list(Categoria.objects.all().order_by('nombre'))
    
    # Pre-filtrar rutinas en DB si hay filtros pesados, sino traer todo (depende del volumen)
    # Si hay búsqueda o filtros, pre-filtramos en DB para reducir RAM
    all_rutinas_qs = Rutina.objects.all().select_related('frecuencia', 'puesto_trabajo', 'categoria')
    
    # Nota: Si el volumen de rutinas es inmenso (>10k), mejor filtrar aquí en DB
    if frecuencia_int:
        all_rutinas_qs = all_rutinas_qs.filter(frecuencia_id=frecuencia_int)
    if puesto_int:
        all_rutinas_qs = all_rutinas_qs.filter(puesto_trabajo_id=puesto_int)
    if search:
        all_rutinas_qs = all_rutinas_qs.filter(
            Q(nombre__icontains=search) | 
            Q(codigo_rutina__icontains=search) |
            Q(descripcion__icontains=search)
        )
    
    all_rutinas = list(all_rutinas_qs)
    
    # Construir el árbol jerárquico en memoria
    tree = build_in_memory_tree(all_categories, all_rutinas, frecuencia_int, puesto_int, search)
    
    # Estadísticas y Datos para Formularios
    frecuencias = Frecuencia.objects.all().order_by('nombre')
    puestos = PuestoTrabajo.objects.all().order_by('nombre')
    total_rutinas = Rutina.objects.count()
    
    # Todas las categorías y procedimientos para el select de creación/edición
    todas_categorias = Categoria.objects.all().order_by('nombre')
    procedimientos = Procedimiento.objects.all().order_by('nombre')
    
    return render(request, 'mantenimiento/rutinas_dashboard.html', {
        'tree': tree,
        'frecuencias': frecuencias,
        'puestos': puestos,
        'todas_categorias': todas_categorias,
        'procedimientos': procedimientos,
        'total_rutinas': total_rutinas,
        'frecuencia_selected': frecuencia_int,
        'puesto_selected': puesto_int,
        'search': search
    })


@staff_member_required
def rutina_detail_api(request, pk):
    """API que devuelve detalles de una rutina y su historial de ejecución"""
    from django.http import JsonResponse
    from ..models import OrdenTrabajo, CierreOrdenTrabajo, PasoProcedimiento
    
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
                'admin_url': f"/admin/mantenimiento/rutina/{rutina.id}/change/",
                'procedimiento_id': rutina.procedimiento_estandar_id,
                'pasos': [
                    {
                        'id': p.id,
                        'orden': p.orden, 
                        'descripcion': p.descripcion, 
                        'verificacion': p.verificacion,
                        'tipo_respuesta': p.tipo_respuesta,
                        'valor_objetivo': p.valor_objetivo,
                        'rango_min': p.rango_min,
                        'rango_max': p.rango_max,
                        'unidad_medida': p.unidad_medida
                    }
                    for p in (rutina.procedimiento_estandar.pasos.all().order_by('orden') if rutina.procedimiento_estandar else [])
                ]
            },
            'historial': history_data
        }
        return JsonResponse(data)
    except Rutina.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Rutina no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def procedimiento_detail_api(request, pk):
    """API para obtener los pasos de un procedimiento específico"""
    from .models import Procedimiento
    try:
        procedimiento = Procedimiento.objects.prefetch_related('pasos').get(pk=pk)
        pasos = [
            {
                'id': p.id,
                'orden': p.orden, 
                'descripcion': p.descripcion, 
                'verificacion': p.verificacion,
                'tipo_respuesta': p.tipo_respuesta,
                'valor_objetivo': p.valor_objetivo,
                'rango_min': p.rango_min,
                'rango_max': p.rango_max,
                'unidad_medida': p.unidad_medida
            }
            for p in procedimiento.pasos.all().order_by('orden')
        ]
        return JsonResponse({'status': 'success', 'pasos': pasos})
    except Procedimiento.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Procedimiento no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def rutina_save_api(request):
    """API para crear o actualizar una rutina vía AJAX"""
    from django.http import JsonResponse
    import json
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        data = json.loads(request.body)
        pk = data.get('id')
        
        if pk:
            rutina = Rutina.objects.get(pk=pk)
        else:
            rutina = Rutina()
            
        rutina.nombre = data.get('nombre')
        rutina.codigo_rutina = data.get('codigo_rutina')
        rutina.descripcion = data.get('descripcion')
        rutina.herramientas = data.get('herramientas')
        rutina.cantidad_tecnicos = int(data.get('cantidad_tecnicos', 1))
        
        # Foreign Keys
        cat_id = data.get('categoria_id')
        rutina.categoria = Categoria.objects.get(pk=cat_id) if cat_id else None
        
        frec_id = data.get('frecuencia_id')
        rutina.frecuencia = Frecuencia.objects.get(pk=frec_id) if frec_id else None
        
        puesto_id = data.get('puesto_trabajo_id')
        rutina.puesto_trabajo = PuestoTrabajo.objects.get(pk=puesto_id) if puesto_id else None
        
        proc_id = data.get('procedimiento_estandar_id')
        rutina.procedimiento_estandar = Procedimiento.objects.get(pk=proc_id) if proc_id else None
        
        # DurationField handling (HH:MM:SS)
        from datetime import timedelta
        tiempo_str = data.get('tiempo_estimado')
        if tiempo_str:
            h, m, s = map(int, tiempo_str.split(':'))
            rutina.tiempo_estimado = timedelta(hours=h, minutes=m, seconds=s)
        
        rutina.save()
        
        return JsonResponse({
            'status': 'success', 
            'message': 'Rutina guardada correctamente',
            'rutina_id': rutina.id
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def procedimiento_save_api(request):
    """API para guardar los pasos de un procedimiento estándar de forma atómica"""
    from django.http import JsonResponse
    from django.db import transaction
    import json
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        data = json.loads(request.body)
        proc_id = data.get('procedimiento_id')
        pasos_data = data.get('pasos', [])
        
        if not proc_id:
            return JsonResponse({'status': 'error', 'message': 'ID de procedimiento requerido'}, status=400)
            
        with transaction.atomic():
            procedimiento = Procedimiento.objects.get(pk=proc_id)
            
            # 1. Obtener IDs de pasos actuales para controlar borrados
            existing_pasos = {p.id: p for p in procedimiento.pasos.all()}
            new_paso_ids = []
            
            for i, p_data in enumerate(pasos_data):
                p_id = p_data.get('id')
                if p_id and int(p_id) in existing_pasos:
                    paso = existing_pasos[int(p_id)]
                else:
                    paso = PasoProcedimiento(procedimiento=procedimiento)
                
                paso.orden = i + 1
                paso.descripcion = p_data.get('descripcion', '')
                paso.verificacion = p_data.get('verificacion', '')
                paso.tipo_respuesta = p_data.get('tipo_respuesta', 'INSTRUCCION')
                paso.unidad_medida = p_data.get('unidad_medida', '')
                
                # Campos numéricos
                try:
                    v_obj = p_data.get('valor_objetivo')
                    paso.valor_objetivo = float(v_obj) if v_obj and str(v_obj).strip() else None
                    r_min = p_data.get('rango_min')
                    paso.rango_min = float(r_min) if r_min and str(r_min).strip() else None
                    r_max = p_data.get('rango_max')
                    paso.rango_max = float(r_max) if r_max and str(r_max).strip() else None
                except (ValueError, TypeError):
                    pass
                
                paso.save()
                new_paso_ids.append(paso.id)
            
            # 2. Borrar pasos que no vinieron en el nuevo set
            PasoProcedimiento.objects.filter(procedimiento=procedimiento).exclude(id__in=new_paso_ids).delete()
            
        return JsonResponse({'status': 'success', 'message': 'Procedimiento actualizado correctamente'})
        
    except Procedimiento.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Procedimiento no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@staff_member_required
def rutina_delete_api(request, pk):
    """API para eliminar una rutina"""
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
        
    try:
        rutina = Rutina.objects.get(pk=pk)
        rutina.delete()
        return JsonResponse({'status': 'success', 'message': 'Rutina eliminada correctamente'})
    except Rutina.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'La rutina no existe'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
