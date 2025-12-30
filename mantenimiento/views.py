
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from .models import OrdenTrabajo, Rutina, Categoria
from datetime import datetime, date, timedelta
import collections

import calendar

def calendario_mantenimiento(request):
    year = int(request.GET.get('year', date.today().year))
    
    # Obtener todas las órdenes del año
    ordenes = OrdenTrabajo.objects.filter(
        inicio_programado__year=year
    ).select_related(
        'rutina__categoria',
        'rutina__frecuencia',
        'ubicacion',
        'programacion__horario'
    ).prefetch_related(
        'programacion__horario__dias',
        'activos'
    ).order_by(
        'rutina__categoria__nombre',
        'rutina__nombre',
        'inicio_programado'
    )
    
    # Optimización: Precargar categorías en memoria para evitar N+1 al usar get_root()
    categorias_full = {c.id: c for c in Categoria.objects.all()}
    for cat in categorias_full.values():
        if cat.padre_id:
            cat.padre = categorias_full.get(cat.padre_id)

    # Re-vincular las categorías de las rutinas de las OTs con las del mapa manual
    for ot in ordenes:
        if ot.rutina and ot.rutina.categoria_id:
            ot.rutina.categoria = categorias_full.get(ot.rutina.categoria_id)
    MESES_NOMBRES = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
    
    meses_info = []
    total_weeks = 0
    for i, nombre in enumerate(MESES_NOMBRES):
        m_num = i + 1
        days_in_month = calendar.monthrange(year, m_num)[1]
        # Cálculo dinámico de semanas (bloques de 7 días)
        num_weeks = (days_in_month - 1) // 7 + 1
        meses_info.append({
            'nombre': nombre,
            'num': m_num,
            'semanas': list(range(1, num_weeks + 1))
        })
        total_weeks += num_weeks

    tree = {}

    # Identificar órdenes y agruparlas
    for ot in ordenes:
        rut = ot.rutina
        cat = rut.categoria
        
        if cat:
            # Simplificamos: Disciplina = Raíz, Sub-Disciplina = Categoría Actual
            # Nota: get_root() es eficiente en MPTT
            dis_name = cat.get_root().nombre
            sub_name = cat.nombre
        else:
            dis_name = "SIN CATEGORÍA"
            sub_name = "GENERAL"
            
        frec = rut.frecuencia
        
        d_key = dis_name
        s_key = sub_name
        # Use frec.dias for sorting
        f_key = (frec.dias, frec.nombre) if frec and frec.dias is not None else (float('inf'), "SIN FRECUENCIA")
        r_key = rut.id

        if d_key not in tree:
            tree[d_key] = {}
        if s_key not in tree[d_key]:
            tree[d_key][s_key] = {}
        if f_key not in tree[d_key][s_key]:
            tree[d_key][s_key][f_key] = {}
            
        if r_key not in tree[d_key][s_key][f_key]:
            horario_obj = ot.programacion.horario if ot.programacion else None
            tree[d_key][s_key][f_key][r_key] = {
                'nombre': rut.nombre,
                'descripcion': rut.descripcion or "Sin descripción",
                'horario_nombre': horario_obj.nombre if horario_obj else "N/A",
                'horario_completo': horario_obj.resumen_corto() if horario_obj else "N/A",
                'matrix': collections.defaultdict(list)
            }
        
        mes = ot.inicio_programado.month
        dia = ot.inicio_programado.day
        semana = (dia - 1) // 7 + 1
        
        # Guardar info de la orden para el popup
        order_info = {
            'id': ot.id,
            'ubicacion': ot.ubicacion.nombre if ot.ubicacion else "S/A",
            'activos': [a.nombre for a in ot.activos.all()],
            'inicio': ot.inicio_programado.strftime('%H:%M'),
            'fin': ot.fin_programado.strftime('%H:%M'),
            'fecha': ot.inicio_programado.strftime('%d/%m/%Y'),
            'estado': ot.estado
        }
        tree[d_key][s_key][f_key][r_key]['matrix'][(mes, semana)].append(order_info)

    def group_locations(order_list):
        if not order_list: return None
        
        # Extraer nombres para la lógica de agrupación
        loc_names = sorted(list(set([o['ubicacion'] for o in order_list])))
        
        if len(loc_names) == 1:
            return {
                'summary': loc_names[0], 
                'items': order_list, 
                'is_group': len(order_list) > 1
            }
        
        import re
        parts = []
        for loc in loc_names:
            match = re.match(r"^(.*?)\s*(\d+)$", loc)
            if match:
                parts.append({'prefix': match.group(1), 'num': int(match.group(2)), 'full': loc})
            else:
                parts.append({'prefix': loc, 'num': None, 'full': loc})
        
        prefixes = collections.defaultdict(list)
        for p in parts:
            prefixes[p['prefix']].append(p)
            
        summary_parts = []
        for pref, items in prefixes.items():
            nums = [it['num'] for it in items if it['num'] is not None]
            if len(nums) > 1:
                nums.sort()
                # Check for consecutive numbers if needed, but for now simple range
                plural_pref = pref
                if pref.lower() == 'nivel':
                    plural_pref = 'Niveles'
                elif pref.lower() == 'piso':
                    plural_pref = 'Pisos'
                elif pref.lower() == 'aula':
                    plural_pref = 'Aulas'
                elif not pref.endswith('s'):
                    plural_pref = f"{pref}s"
                
                summary_parts.append(f"{plural_pref} {nums[0]} al {nums[-1]}")
            else:
                for it in items:
                    summary_parts.append(it['full'])
        
        return {
            'summary': ", ".join(summary_parts),
            'items': order_list,
            'is_group': True
        }

    # Convertir a listas ordenadas para el template con agregación
    disciplinas_final = []
    for d_nom in sorted(tree.keys()):
        subs_final = []
        d_agregado = collections.defaultdict(bool)
        
        for s_nom in sorted(tree[d_nom].keys()):
            frefs_final = []
            s_agregado = collections.defaultdict(bool)
            
            for f_key_tuple in sorted(tree[d_nom][s_nom].keys()):
                ruts_final = []
                f_agregado = collections.defaultdict(bool)
                
                for r_id in sorted(tree[d_nom][s_nom][f_key_tuple].keys()):
                    r_data = tree[d_nom][s_nom][f_key_tuple][r_id]
                    celdas = []
                    for m_info in meses_info:
                        for s in m_info['semanas']:
                            celda_val = group_locations(r_data['matrix'][(m_info['num'], s)])
                            celdas.append(celda_val)
                            if celda_val:
                                f_agregado[(m_info['num'], s)] = True
                                s_agregado[(m_info['num'], s)] = True
                                d_agregado[(m_info['num'], s)] = True
                    
                    ruts_final.append({
                        'nombre': r_data['nombre'],
                        'descripcion': r_data['descripcion'],
                        'horario': r_data['horario_completo'],
                        'celdas': celdas
                    })
                
                # Resumen para Frecuencia
                f_celdas_resumen = []
                for m_info in meses_info:
                    for s in m_info['semanas']:
                        f_celdas_resumen.append({'active': f_agregado[(m_info['num'], s)]})

                frefs_final.append({
                    'nombre': f_key_tuple[1],
                    'rutinas': ruts_final,
                    'celdas_resumen': f_celdas_resumen
                })
            
            # Resumen para Sub-Disciplina
            s_celdas_resumen = []
            for m_info in meses_info:
                for s in m_info['semanas']:
                    s_celdas_resumen.append({'active': s_agregado[(m_info['num'], s)]})

            subs_final.append({
                'nombre': s_nom,
                'frecuencias': frefs_final,
                'celdas_resumen': s_celdas_resumen
            })
        
        # Resumen para Disciplina
        d_celdas_resumen = []
        for m_info in meses_info:
            for s in m_info['semanas']:
                d_celdas_resumen.append({'active': d_agregado[(m_info['num'], s)]})

        disciplinas_final.append({
            'nombre': d_nom,
            'subs': subs_final,
            'celdas_resumen': d_celdas_resumen
        })

    # Manually inject UI Config as fallback
    try:
        from core.models import ConfiguracionUI
        ui_config_obj = ConfiguracionUI.objects.first()
    except Exception as e:
        print(f"Error loading UI Config: {e}")
        ui_config_obj = None

    return render(request, 'mantenimiento/calendario.html', {
        'disciplinas': disciplinas_final,
        'year': year,
        'meses': meses_info,
        'total_colspan': total_weeks + 2,
        'ui_config': ui_config_obj
    })


def calendario_detallado(request):
    year = int(request.GET.get('year', date.today().year))
    
    ordenes = OrdenTrabajo.objects.filter(
        inicio_programado__year=year
    ).select_related(
        'rutina__categoria',
        'rutina__frecuencia',
        'ubicacion'
    ).order_by(
        'rutina__categoria__nombre',
        'rutina__nombre',
        'ubicacion__nombre',
        'inicio_programado'
    )
    
    categorias_full = {c.id: c for c in Categoria.objects.all()}
    for cat in categorias_full.values():
        if cat.padre_id:
            cat.padre = categorias_full.get(cat.padre_id)

    MESES_NOMBRES = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
    meses_info = []
    total_weeks = 0
    for i, nombre in enumerate(MESES_NOMBRES):
        m_num = i + 1
        days_in_month = calendar.monthrange(year, m_num)[1]
        num_weeks = (days_in_month - 1) // 7 + 1
        meses_info.append({
            'nombre': nombre,
            'num': m_num,
            'semanas': list(range(1, num_weeks + 1))
        })
        total_weeks += num_weeks

    tree = {}

    for ot in ordenes:
        rut = ot.rutina
        if not rut: continue
        
        cat = rut.categoria
        if cat:
            cat = categorias_full.get(cat.id) or cat
            dis_name = cat.get_root().nombre
            sub_name = cat.nombre
        else:
            dis_name = "SIN CATEGORÍA"
            sub_name = "GENERAL"
            
        frec = rut.frecuencia
        f_key = (frec.dias, frec.nombre) if frec and frec.dias is not None else (float('inf'), "SIN FRECUENCIA")
        r_key = rut.id
        loc_name = ot.ubicacion.nombre if ot.ubicacion else "S/A"

        if dis_name not in tree: tree[dis_name] = {}
        if sub_name not in tree[dis_name]: tree[dis_name][sub_name] = {}
        if f_key not in tree[dis_name][sub_name]: tree[dis_name][sub_name][f_key] = {}
        if r_key not in tree[dis_name][sub_name][f_key]:
            tree[dis_name][sub_name][f_key][r_key] = {
                'nombre': rut.nombre,
                'ubicaciones': {}
            }
            
        if loc_name not in tree[dis_name][sub_name][f_key][r_key]['ubicaciones']:
            tree[dis_name][sub_name][f_key][r_key]['ubicaciones'][loc_name] = {
                'matrix': collections.defaultdict(bool),
                'orders': collections.defaultdict(list)
            }
        
        mes = ot.inicio_programado.month
        dia = ot.inicio_programado.day
        semana = (dia - 1) // 7 + 1
        
        tree[dis_name][sub_name][f_key][r_key]['ubicaciones'][loc_name]['matrix'][(mes, semana)] = True
        tree[dis_name][sub_name][f_key][r_key]['ubicaciones'][loc_name]['orders'][(mes, semana)].append({
            'id': ot.id,
            'inicio': ot.inicio_programado.strftime('%H:%M'),
            'fin': ot.fin_programado.strftime('%H:%M'),
            'fecha': ot.inicio_programado.strftime('%d/%m/%Y'),
            'estado': ot.estado
        })

    # Estructura final para el template con agregación
    disciplinas_final = []
    for d_nom in sorted(tree.keys()):
        subs_final = []
        d_agregado = collections.defaultdict(bool)
        
        for s_nom in sorted(tree[d_nom].keys()):
            frefs_final = []
            s_agregado = collections.defaultdict(bool)
            
            for f_key_tuple in sorted(tree[d_nom][s_nom].keys()):
                ruts_final = []
                f_agregado = collections.defaultdict(bool)
                
                for r_id in sorted(tree[d_nom][s_nom][f_key_tuple].keys()):
                    r_data = tree[d_nom][s_nom][f_key_tuple][r_id]
                    locs_final = []
                    r_agregado = collections.defaultdict(bool)
                    
                    for l_name in sorted(r_data['ubicaciones'].keys()):
                        l_data = r_data['ubicaciones'][l_name]
                        celdas = []
                        for m_info in meses_info:
                            for s in m_info['semanas']:
                                has_ot = l_data['matrix'][(m_info['num'], s)]
                                o_list = l_data['orders'][(m_info['num'], s)]
                                celdas.append({
                                    'active': has_ot,
                                    'items': o_list
                                })
                                if has_ot:
                                    r_agregado[(m_info['num'], s)] = True
                                    f_agregado[(m_info['num'], s)] = True
                                    s_agregado[(m_info['num'], s)] = True
                                    d_agregado[(m_info['num'], s)] = True
                        
                        locs_final.append({
                            'nombre': l_name,
                            'celdas': celdas
                        })
                    
                    # Celdas de resumen para Rutina
                    r_celdas_resumen = []
                    for m_info in meses_info:
                        for s in m_info['semanas']:
                            r_celdas_resumen.append({'active': r_agregado[(m_info['num'], s)]})

                    ruts_final.append({
                        'nombre': r_data['nombre'],
                        'ubicaciones': locs_final,
                        'celdas_resumen': r_celdas_resumen
                    })
                
                # Celdas de resumen para Frecuencia
                f_celdas_resumen = []
                for m_info in meses_info:
                    for s in m_info['semanas']:
                        f_celdas_resumen.append({'active': f_agregado[(m_info['num'], s)]})

                frefs_final.append({
                    'nombre': f_key_tuple[1],
                    'rutinas': ruts_final,
                    'celdas_resumen': f_celdas_resumen
                })
            
            # Celdas de resumen para Sub-Disciplina
            s_celdas_resumen = []
            for m_info in meses_info:
                for s in m_info['semanas']:
                    s_celdas_resumen.append({'active': s_agregado[(m_info['num'], s)]})

            subs_final.append({
                'nombre': s_nom,
                'frecuencias': frefs_final,
                'celdas_resumen': s_celdas_resumen
            })
        
        # Celdas de resumen para Disciplina
        d_celdas_resumen = []
        for m_info in meses_info:
            for s in m_info['semanas']:
                d_celdas_resumen.append({'active': d_agregado[(m_info['num'], s)]})

        disciplinas_final.append({
            'nombre': d_nom,
            'subs': subs_final,
            'celdas_resumen': d_celdas_resumen
        })

    # Resumen de estadísticas
    count_disciplinas = len(tree.keys())
    count_rutinas = sum(len(tree[d][s][f].keys()) for d in tree for s in tree[d] for f in tree[d][s])
    unique_locations = set()
    for d in tree:
        for s in tree[d]:
            for f in tree[d][s]:
                for r in tree[d][s][f]:
                    for loc in tree[d][s][f][r]['ubicaciones']:
                        unique_locations.add(loc)
    count_ubicaciones = len(unique_locations)
    total_ot = ordenes.count()

    try:
        from core.models import ConfiguracionUI
        ui_config_obj = ConfiguracionUI.objects.first()
    except Exception as e:
        ui_config_obj = None

    return render(request, 'mantenimiento/calendario_detallado.html', {
        'disciplinas': disciplinas_final,
        'year': year,
        'meses': meses_info,
        'total_colspan': total_weeks + 1,
        'ui_config': ui_config_obj,
        'resumen': {
            'disciplinas': count_disciplinas,
            'rutinas': count_rutinas,
            'ubicaciones': count_ubicaciones,
            'ordenes': total_ot
        }
    })


@staff_member_required
def cronograma_mantenimiento_visual(request):
    from activos.models import Ubicacion
    year = int(request.GET.get('year', datetime.now().year))
    view_mode = request.GET.get('view_mode', 'sistema') # 'sistema' o 'ubicacion'
    ubicacion_id = request.GET.get('ubicacion_id')
    
    # Obtener todas las ubicaciones raíz para el filtro
    ubicaciones_roots = Ubicacion.objects.filter(padre__isnull=True).order_by('nombre')
    
    # Filtro base para las órdenes
    filtros = {'inicio_programado__year': year}
    
    if ubicacion_id:
        try:
            area_sel = Ubicacion.objects.get(id=ubicacion_id)
            desc_ids = area_sel.get_descendants(include_self=True).values_list('id', flat=True)
            filtros['ubicacion_id__in'] = desc_ids
        except Ubicacion.DoesNotExist:
            pass

    # Obtener todas las órdenes del año filtradas
    ordenes = OrdenTrabajo.objects.filter(
        **filtros
    ).select_related(
        'ubicacion', 
        'rutina__categoria', 
        'rutina__frecuencia',
        'programacion__horario'
    ).values(
        'id', 'rutina__nombre', 'ubicacion__nombre', 
        'rutina__categoria_id', 'inicio_programado', 'estado',
        'programacion__horario__color'
    )
    
    # Precargar categorías para encontrar raíces (sistemas)
    categorias = {c.id: c for c in Categoria.objects.all()}
    for c in categorias.values():
        if c.padre_id:
            c.padre = categorias.get(c.padre_id)

    # Estructura para agrupar: {RootLabel: {SubLabel: {RoutineLabel: {WeekIdx: [ots]}}}}
    grupos_dict = collections.defaultdict(
        lambda: collections.defaultdict(
            lambda: collections.defaultdict(
                lambda: collections.defaultdict(list)
            )
        )
    )
    
    for ot in ordenes:
        dia_año = ot['inicio_programado'].timetuple().tm_yday
        semana_idx = (dia_año - 1) // 7
        if semana_idx > 51: semana_idx = 51

        if view_mode == 'ubicacion':
            # Para ubicación, podríamos intentar: Padre -> Ubicación -> Rutina
            group_label = ot['ubicacion__nombre'] or "S/U"
            sub_label = "General" # Simplificado por ahora o podríamos buscar el padre de la ubicación
            routine_label = ot['rutina__nombre'] or "General"
        else: # sistema
            cat_id = ot['rutina__categoria_id']
            if cat_id and cat_id in categorias:
                root = categorias[cat_id].get_root()
                group_label = root.nombre
                # La subcategoría es la categoría directa, a menos que sea la misma raíz
                sub_label = categorias[cat_id].nombre if categorias[cat_id].id != root.id else "General"
            else:
                group_label = "General / Otros"
                sub_label = "Sin Categoría"
            routine_label = ot['rutina__nombre'] or "General"
        
        grupos_dict[group_label][sub_label][routine_label][semana_idx].append(ot)

    # Preparar datos finales
    datos_finales = []
    meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    
    # Generar 52 semanas
    semanas = []
    base_date = datetime(year, 1, 1)
    if base_date.weekday() != 0:
        base_date += timedelta(days=(7 - base_date.weekday()))
    
    for i in range(52):
        start_week = base_date + timedelta(weeks=i)
        semanas.append({'n': i + 1, 'inicio': start_week, 'mes': meses_nombres[start_week.month - 1]})

    for g_label, subs_map in sorted(grupos_dict.items()):
        # Celdas de resumen del sistema raíz
        celdas_grupo = []
        best_color = '#3b82f6'
        color_found = False

        for i in range(52):
            any_in_week = False
            for s_label, routines_map in subs_map.items():
                if any(routines_map[r][i] for r in routines_map):
                    any_in_week = True
                    break
            celdas_grupo.append({'active': any_in_week})
        
        subgrupos_nested = []
        for s_label, routines_map in sorted(subs_map.items()):
            # Celdas de resumen de la subcategoría
            celdas_sub = []
            for i in range(52):
                any_in_week = any(routines_map[r][i] for r in routines_map)
                celdas_sub.append({'active': any_in_week})

            rutinas_nested = []
            for r_label, weeks_map in sorted(routines_map.items()):
                celdas_rutina = []
                routine_color = '#3b82f6'
                for i in range(52):
                    ots = weeks_map.get(i, [])
                    if ots and not color_found:
                        best_color = ots[0]['programacion__horario__color'] or '#3b82f6'
                        color_found = True
                    
                    if ots:
                        routine_color = ots[0]['programacion__horario__color'] or '#3b82f6'

                    celdas_rutina.append({
                        'active': bool(ots),
                        'count': len(ots),
                        'info': ", ".join(set([o['rutina__nombre'] if view_mode == 'ubicacion' else o['ubicacion__nombre'] or 'S/U' for o in ots]))
                    })
                rutinas_nested.append({
                    'label': r_label,
                    'celdas': celdas_rutina,
                    'color': routine_color
                })
            
            subgrupos_nested.append({
                'label': s_label,
                'celdas': celdas_sub,
                'rutinas': rutinas_nested
            })

        datos_finales.append({
            'label': g_label,
            'celdas': celdas_grupo,
            'subgrupos': subgrupos_nested,
            'color': best_color if color_found else ('#c00000' if view_mode == 'sistema' else '#3b82f6')
        })

    # Agrupar por Mes para el Header
    meses_header = []
    for m_name in meses_nombres:
        count = len([s for s in semanas if s['mes'] == m_name])
        if count:
            meses_header.append({'nombre': m_name, 'count': count})

    return render(request, 'mantenimiento/cronograma.html', {
        'items': datos_finales,
        'semanas': semanas,
        'meses_header': meses_header,
        'year': year,
        'view_mode': view_mode,
        'ubicaciones_roots': ubicaciones_roots,
        'current_ubi': int(ubicacion_id) if ubicacion_id else None,
    })
