
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
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
    programacion_id = request.GET.get('programacion_id')
    
    # Obtener todas las ubicaciones raíz para el filtro (solo Edificios)
    ubicaciones_roots = Ubicacion.objects.filter(padre__isnull=True, tipo='EDIFICIO').order_by('nombre')
    
    # Filtro base para las órdenes
    filtros = {'inicio_programado__year': year}
    
    if programacion_id:
        filtros['programacion_id'] = programacion_id
    
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
        'id', 'rutina__nombre', 'ubicacion__nombre', 'ubicacion_id',
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
    
    # Mapa de ubicaciones para jerarquía (ID -> Objeto)
    all_locs = Ubicacion.objects.all()
    loc_map = {u.id: u for u in all_locs}

    def get_edificio_root(loc_id):
        curr = loc_map.get(loc_id)
        while curr:
            if curr.tipo == 'EDIFICIO':
                return curr
            curr = loc_map.get(curr.padre_id)
        return None

    for ot in ordenes:
        dia_año = ot['inicio_programado'].timetuple().tm_yday
        semana_idx = (dia_año - 1) // 7
        if semana_idx > 51: semana_idx = 51

        if view_mode == 'ubicacion':
            # Buscar el edificio padre
            root_edificio = get_edificio_root(ot['ubicacion_id'])
            
            # Si estamos viendo "Todas" y no tiene edificio, lo descartamos según requerimiento
            # "quisiera que me mostrara solo las que estan categorizadas como Edificio"
            if not ubicacion_id and not root_edificio:
                continue

            if root_edificio:
                group_label = root_edificio.nombre
            else:
                # Fallback para cuando se filtra una ubicación específica que no está en edificio
                group_label = ot['ubicacion__nombre'] or "S/U"

            # Sub-nivel es la ubicación específica (si es distinta al edificio)
            loc_nombre = ot['ubicacion__nombre'] or "General"
            if root_edificio and loc_nombre == root_edificio.nombre:
                sub_label = "General"
            else:
                sub_label = loc_nombre

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
    for i, m_name in enumerate(meses_nombres):
        count = len([s for s in semanas if s['mes'] == m_name])
        if count:
            meses_header.append({'nombre': m_name, 'count': count, 'num': i + 1})

    # Marcar la ubicación seleccionada para evitar comparaciones en el template (evita errores de sintaxis por formateadores)
    current_ubi_id = int(ubicacion_id) if ubicacion_id else None
    for u in ubicaciones_roots:
        u.is_selected = (u.id == current_ubi_id)

    return render(request, 'mantenimiento/cronograma_fix.html', {
        'items': datos_finales,
        'semanas': semanas,
        'meses_header': meses_header,
        'year': year,
        'view_mode': view_mode,
        'ubicaciones_roots': ubicaciones_roots,
        'current_ubi': current_ubi_id,
        'programacion_id': programacion_id,
    })


@staff_member_required
def detalle_mes(request, year, month):
    from activos.models import Ubicacion
    import calendar
    programacion_id = request.GET.get('programacion_id')
    
    # Obtener número de días del mes
    try:
        _, num_days = calendar.monthrange(year, month)
    except:
        num_days = 31
        
    days_range = range(1, num_days + 1)
    
    # Filtro base
    filtros = {
        'inicio_programado__year': year,
        'inicio_programado__month': month
    }
    
    if programacion_id:
        filtros['programacion_id'] = programacion_id
    
    ordenes = OrdenTrabajo.objects.filter(**filtros).select_related(
        'rutina__categoria', 
        'rutina__frecuencia',
        'ubicacion',
        'programacion__horario'
    ).prefetch_related('activos', 'rutina__categoria')
    
    # Precargar categorías
    categs = {c.id: c for c in Categoria.objects.all()}
    for c in categs.values():
        if c.padre_id: c.padre = categs.get(c.padre_id)

    # Estructura: System -> Sub -> Routine -> Location -> Asset -> {day: list_ots}
    tree = collections.defaultdict(
        lambda: collections.defaultdict(
            lambda: collections.defaultdict(
                lambda: collections.defaultdict(
                    lambda: collections.defaultdict(
                        lambda: collections.defaultdict(list)
                    )
                )
            )
        )
    )
    
    system_colors = {}

    for ot in ordenes:
        day = ot.inicio_programado.day
        
        cat = ot.rutina.categoria if ot.rutina else None
        
        if cat and cat.id in categs:
            full_cat = categs[cat.id]
            root = full_cat.get_root()
            sys_name = root.nombre
            sub_name = full_cat.nombre if full_cat.id != root.id else "General"
            
            if sys_name not in system_colors:
                system_colors[sys_name] = ot.programacion.horario.color if ot.programacion and ot.programacion.horario else "#64748b"
        else:
            sys_name = "Sin Categoría / Otros"
            sub_name = "General"
            if sys_name not in system_colors: system_colors[sys_name] = "#64748b"
            
        rutina_name = ot.rutina.nombre if ot.rutina else "OT Sin Rutina"
        ubi_name = ot.ubicacion.nombre if ot.ubicacion else "Ubicación No Def."
        
        # Un OT puede tener múltiples activos.
        activos = list(ot.activos.all())
        if not activos:
            tree[sys_name][sub_name][rutina_name][ubi_name][(None, "General")][day].append(ot)
        else:
            for a in activos:
                tree[sys_name][sub_name][rutina_name][ubi_name][(a.id, a.nombre)][day].append(ot)
        
    # Estructura final para el template (Anidada: Sys -> Sub -> Rut -> Ubi -> Asset)
    final_tree = []
    
    for sys in sorted(tree.keys()):
        sys_subs = []
        sys_day_active = collections.defaultdict(bool)
        
        for sub in sorted(tree[sys].keys()):
            sub_routines = []
            sub_day_active = collections.defaultdict(bool)
            
            for rut in sorted(tree[sys][sub].keys()):
                rut_ubis = []
                rut_day_active = collections.defaultdict(bool)
                
                for ubi in sorted(tree[sys][sub][rut].keys()):
                    ubi_assets = []
                    ubi_day_active = collections.defaultdict(bool)
                    
                    # asset_key es (id, nombre)
                    for asset_key in sorted(tree[sys][sub][rut][ubi].keys(), key=lambda x: x[1]):
                        asset_id, asset_label = asset_key
                        asset_cells = []
                        for d in days_range:
                            ots = tree[sys][sub][rut][ubi][asset_key].get(d, [])
                            has_data = len(ots) > 0
                            asset_cells.append({'day': d, 'ots': ots, 'active': has_data})
                            if has_data:
                                ubi_day_active[d] = True
                                rut_day_active[d] = True
                                sub_day_active[d] = True
                                sys_day_active[d] = True
                                
                        ubi_assets.append({'label': asset_label, 'id': asset_id, 'celdas': asset_cells})
                    
                    ubi_summary_cells = [{'day': d, 'active': ubi_day_active[d]} for d in days_range]
                    rut_ubis.append({'label': ubi, 'celdas': ubi_summary_cells, 'activos': ubi_assets})
                
                rut_summary_cells = [{'day': d, 'active': rut_day_active[d]} for d in days_range]
                sub_routines.append({'label': rut, 'celdas': rut_summary_cells, 'ubicaciones': rut_ubis})
            
            sub_summary_cells = [{'day': d, 'active': sub_day_active[d]} for d in days_range]
            sys_subs.append({'label': sub, 'celdas': sub_summary_cells, 'rutinas': sub_routines})
            
        sys_summary_cells = [{'day': d, 'active': sys_day_active[d]} for d in days_range]
        final_tree.append({
            'label': sys,
            'color': system_colors.get(sys, "#64748b"),
            'celdas': sys_summary_cells,
            'subs': sys_subs
        })

    meses_es = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    return render(request, 'mantenimiento/detalle_mes.html', {
        'year': year,
        'month': month,
        'mes_nombre': meses_es[month],
        'days_range': days_range,
        'tree': final_tree,
        'programacion_id': programacion_id
    })

@staff_member_required
@require_POST
@csrf_exempt
def api_update_ot_date(request):
    import json
    from datetime import datetime
    try:
        data = json.loads(request.body)
        ot_id = data.get('ot_id')
        nueva_fecha_str = data.get('nueva_fecha')
        
        if not ot_id or not nueva_fecha_str:
            return JsonResponse({'status': 'error', 'message': 'Datos incompletos'}, status=400)
            
        ot = OrdenTrabajo.objects.get(id=ot_id)
        nueva_fecha = datetime.strptime(nueva_fecha_str, '%Y-%m-%d').date()
        
        # Calcular diferencia para mover el fin_programado también
        delta = nueva_fecha - ot.inicio_programado.date()
        
        ot.inicio_programado = ot.inicio_programado + delta
        ot.fin_programado = ot.fin_programado + delta
        ot.save()
        
        return JsonResponse({'status': 'success', 'message': f'Orden #{ot_id} movida al {nueva_fecha_str}'})
    except OrdenTrabajo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Orden no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
@require_POST
@csrf_exempt
def api_split_ot_asset(request):
    import json
    try:
        data = json.loads(request.body)
        ot_id = data.get('ot_id')
        asset_id = data.get('asset_id')
        
        if not ot_id or not asset_id:
            return JsonResponse({'status': 'error', 'message': 'Datos incompletos'}, status=400)
            
        ot = OrdenTrabajo.objects.prefetch_related('activos').get(id=ot_id)
        
        if ot.activos.count() <= 1:
            return JsonResponse({'status': 'error', 'message': 'La orden solo tiene un activo, no se puede separar.'}, status=400)
            
        from activos.models import Activo
        asset = Activo.objects.get(id=asset_id)
        
        # Crear nueva orden clonando la original
        new_ot = OrdenTrabajo.objects.create(
            tipo=ot.tipo,
            prioridad=ot.prioridad,
            rutina=ot.rutina,
            aviso=ot.aviso,
            tecnico=ot.tecnico,
            ubicacion=ot.ubicacion,
            programacion=ot.programacion,
            planificacion=ot.planificacion,
            inicio_programado=ot.inicio_programado,
            fin_programado=ot.fin_programado,
            estado=ot.estado,
            notas=f"Orden separada de OT #{ot.id}. \n" + (ot.notas or "")
        )
        new_ot.activos.add(asset)
        
        # Quitar el activo de la orden original
        ot.activos.remove(asset)
        
        # Recalcular tiempos si la rutina tiene tiempo estimado
        if ot.rutina and ot.rutina.tiempo_estimado:
            t = ot.rutina.tiempo_estimado
            ot.fin_programado = ot.inicio_programado + (t * ot.activos.count())
            new_ot.fin_programado = new_ot.inicio_programado + t
            ot.save()
            new_ot.save()
            
        return JsonResponse({
            'status': 'success',
            'message': f'Activo {asset.nombre} separado en la nueva Orden #{new_ot.id}'
        })
    except (OrdenTrabajo.DoesNotExist, Activo.DoesNotExist):
        return JsonResponse({'status': 'error', 'message': 'Orden o Activo no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
@require_POST
@csrf_exempt
def api_merge_ots(request):
    import json
    try:
        data = json.loads(request.body)
        ot_ids = data.get('ot_ids', [])

        if not ot_ids or len(ot_ids) < 2:
            return JsonResponse({'status': 'error', 'message': 'Se requieren al menos 2 órdenes para fusionar.'}, status=400)

        ots = list(OrdenTrabajo.objects.filter(id__in=ot_ids).prefetch_related('activos'))

        if len(ots) < 2:
            return JsonResponse({'status': 'error', 'message': 'No se encontraron todas las órdenes solicitadas.'}, status=404)

        # La primera OT de la lista será la maestra
        master_ot = ots[0]
        other_ots = ots[1:]

        consolidated_notes = [master_ot.notas] if master_ot.notas else []

        for ot in other_ots:
            # Transferir activos
            for asset in ot.activos.all():
                master_ot.activos.add(asset)

            # Consolidar notas
            if ot.notas:
                consolidated_notes.append(f"--- Notas OT #{ot.id} ---\n{ot.notas}")

            # Eliminar la OT redundante
            ot.delete()

        master_ot.notas = "\n\n".join(consolidated_notes)

        # Recalcular tiempos si aplica
        if master_ot.rutina and master_ot.rutina.tiempo_estimado:
            t = master_ot.rutina.tiempo_estimado
            master_ot.fin_programado = master_ot.inicio_programado + (t * master_ot.activos.count())

        master_ot.save()

        return JsonResponse({
            'status': 'success',
            'message': f'Fusionadas {len(ots)} órdenes en la OT #{master_ot.id}',
            'master_id': master_ot.id
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
@require_POST
@csrf_exempt
def api_bulk_update_ot_dates(request):
    import json
    from datetime import datetime
    try:
        data = json.loads(request.body)
        ot_ids = data.get('ot_ids', [])
        nueva_fecha_str = data.get('nueva_fecha')
        
        if not ot_ids or not nueva_fecha_str:
            return JsonResponse({'status': 'error', 'message': 'Datos incompletos'}, status=400)
            
        nueva_fecha = datetime.strptime(nueva_fecha_str, '%Y-%m-%d').date()
        updated_count = 0
        
        for ot_id in ot_ids:
            try:
                ot = OrdenTrabajo.objects.get(id=ot_id)
                delta = nueva_fecha - ot.inicio_programado.date()
                ot.inicio_programado = ot.inicio_programado + delta
                ot.fin_programado = ot.fin_programado + delta
                ot.save()
                updated_count += 1
            except OrdenTrabajo.DoesNotExist:
                continue
        
        return JsonResponse({'status': 'success', 'message': f'{updated_count} órdenes movidas al {nueva_fecha_str}'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@staff_member_required
@require_POST
@csrf_exempt
def api_get_notifications(request):
    from .models import NotificacionMantenimiento
    notifs = NotificacionMantenimiento.objects.filter(user=request.user, leida=False)
    data = []
    for n in notifs:
        data.append({
            'id': n.id,
            'mensaje': n.mensaje,
            'tipo': n.tipo,
            'creado_en': n.creado_en.strftime('%H:%M:%S')
        })
    return JsonResponse({'status': 'success', 'notificaciones': data})

@staff_member_required
@require_POST
@csrf_exempt
def api_mark_notification_read(request):
    import json
    from .models import NotificacionMantenimiento
    try:
        data = json.loads(request.body)
        notif_id = data.get('notif_id')
        if notif_id:
            NotificacionMantenimiento.objects.filter(id=notif_id, user=request.user).update(leida=True)
        else:
            NotificacionMantenimiento.objects.filter(user=request.user, leida=False).update(leida=True)
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
