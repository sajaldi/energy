from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from ..models import OrdenTrabajo, Rutina, Categoria, Programacion, Aviso, PuestoTrabajo, TecnicoPuesto, RestriccionCalendario
from activos.models import Activo, Ubicacion
from django.utils import timezone
from datetime import datetime, date, timedelta
import collections
import calendar
import math
from django.db.models import Count, Q, Min

@staff_member_required
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
            dis_name = cat.get_root().nombre
            sub_name = cat.nombre
        else:
            dis_name = "SIN CATEGORÍA"
            sub_name = "GENERAL"
            
        frec = rut.frecuencia
        
        d_key = dis_name
        s_key = sub_name
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
        loc_names = sorted(list(set([o['ubicacion'] for o in order_list])))
        if len(loc_names) == 1:
            return {'summary': loc_names[0], 'items': order_list, 'is_group': len(order_list) > 1}
        import re
        parts = []
        for loc in loc_names:
            match = re.match(r"^(.*?)\s*(\d+)$", loc)
            if match:
                parts.append({'prefix': match.group(1), 'num': int(match.group(2)), 'full': loc})
            else:
                parts.append({'prefix': loc, 'num': None, 'full': loc})
        prefixes = collections.defaultdict(list)
        for p in parts: prefixes[p['prefix']].append(p)
        summary_parts = []
        for pref, items in prefixes.items():
            nums = [it['num'] for it in items if it['num'] is not None]
            if len(nums) > 1:
                nums.sort()
                plural_pref = pref
                if pref.lower() == 'nivel': plural_pref = 'Niveles'
                elif pref.lower() == 'piso': plural_pref = 'Pisos'
                elif pref.lower() == 'aula': plural_pref = 'Aulas'
                elif not pref.endswith('s'): plural_pref = f"{pref}s"
                summary_parts.append(f"{plural_pref} {nums[0]} al {nums[-1]}")
            else:
                for it in items: summary_parts.append(it['full'])
        return {'summary': ", ".join(summary_parts), 'items': order_list, 'is_group': True}

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
                    ruts_final.append({'nombre': r_data['nombre'], 'descripcion': r_data['descripcion'], 'horario': r_data['horario_completo'], 'celdas': celdas})
                f_celdas_resumen = [{'active': f_agregado[(m_info['num'], s)]} for m_info in meses_info for s in m_info['semanas']]
                frefs_final.append({'nombre': f_key_tuple[1], 'rutinas': ruts_final, 'celdas_resumen': f_celdas_resumen})
            s_celdas_resumen = [{'active': s_agregado[(m_info['num'], s)]} for m_info in meses_info for s in m_info['semanas']]
            subs_final.append({'nombre': s_nom, 'frecuencias': frefs_final, 'celdas_resumen': s_celdas_resumen})
        d_celdas_resumen = [{'active': d_agregado[(m_info['num'], s)]} for m_info in meses_info for s in m_info['semanas']]
        disciplinas_final.append({'nombre': d_nom, 'subs': subs_final, 'celdas_resumen': d_celdas_resumen})

    try:
        from core.models import ConfiguracionUI
        ui_config_obj = ConfiguracionUI.objects.first()
    except: ui_config_obj = None

    return render(request, 'mantenimiento/calendario.html', {
        'disciplinas': disciplinas_final, 'year': year, 'meses': meses_info, 'total_colspan': total_weeks + 2, 'ui_config': ui_config_obj
    })

@staff_member_required
def calendario_detallado(request):
    year = int(request.GET.get('year', date.today().year))
    ordenes = OrdenTrabajo.objects.filter(inicio_programado__year=year).select_related('rutina__categoria', 'rutina__frecuencia', 'ubicacion').order_by('rutina__categoria__nombre', 'rutina__nombre', 'ubicacion__nombre', 'inicio_programado')
    categorias_full = {c.id: c for c in Categoria.objects.all()}
    for cat in categorias_full.values():
        if cat.padre_id: cat.padre = categorias_full.get(cat.padre_id)
    MESES_NOMBRES = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
    meses_info = []
    total_weeks = 0
    for i, nombre in enumerate(MESES_NOMBRES):
        m_num = i + 1
        days_in_month = calendar.monthrange(year, m_num)[1]
        num_weeks = (days_in_month - 1) // 7 + 1
        meses_info.append({'nombre': nombre, 'num': m_num, 'semanas': list(range(1, num_weeks + 1))})
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
            dis_name = "SIN CATEGORÍA"; sub_name = "GENERAL"
        frec = rut.frecuencia
        f_key = (frec.dias, frec.nombre) if frec and frec.dias is not None else (float('inf'), "SIN FRECUENCIA")
        r_key = rut.id
        loc_name = ot.ubicacion.nombre if ot.ubicacion else "S/A"
        if dis_name not in tree: tree[dis_name] = {}
        if sub_name not in tree[dis_name]: tree[dis_name][sub_name] = {}
        if f_key not in tree[dis_name][sub_name]: tree[dis_name][sub_name][f_key] = {}
        if r_key not in tree[dis_name][sub_name][f_key]: tree[dis_name][sub_name][f_key][r_key] = {'nombre': rut.nombre, 'ubicaciones': {}}
        if loc_name not in tree[dis_name][sub_name][f_key][r_key]['ubicaciones']: tree[dis_name][sub_name][f_key][r_key]['ubicaciones'][loc_name] = {'matrix': collections.defaultdict(bool), 'orders': collections.defaultdict(list)}
        mes = ot.inicio_programado.month; dia = ot.inicio_programado.day; semana = (dia - 1) // 7 + 1
        tree[dis_name][sub_name][f_key][r_key]['ubicaciones'][loc_name]['matrix'][(mes, semana)] = True
        tree[dis_name][sub_name][f_key][r_key]['ubicaciones'][loc_name]['orders'][(mes, semana)].append({'id': ot.id, 'inicio': ot.inicio_programado.strftime('%H:%M'), 'fin': ot.fin_programado.strftime('%H:%M'), 'fecha': ot.inicio_programado.strftime('%d/%m/%Y'), 'estado': ot.estado})
    disciplinas_final = []
    for d_nom in sorted(tree.keys()):
        subs_final = []; d_agregado = collections.defaultdict(bool)
        for s_nom in sorted(tree[d_nom].keys()):
            frefs_final = []; s_agregado = collections.defaultdict(bool)
            for f_key_tuple in sorted(tree[d_nom][s_nom].keys()):
                ruts_final = []; f_agregado = collections.defaultdict(bool)
                for r_id in sorted(tree[d_nom][s_nom][f_key_tuple].keys()):
                    r_data = tree[d_nom][s_nom][f_key_tuple][r_id]; locs_final = []; r_agregado = collections.defaultdict(bool)
                    for l_name in sorted(r_data['ubicaciones'].keys()):
                        l_data = r_data['ubicaciones'][l_name]; celdas = []
                        for m_info in meses_info:
                            for s in m_info['semanas']:
                                has_ot = l_data['matrix'][(m_info['num'], s)]; o_list = l_data['orders'][(m_info['num'], s)]
                                celdas.append({'active': has_ot, 'items': o_list})
                                if has_ot: r_agregado[(m_info['num'], s)] = True; f_agregado[(m_info['num'], s)] = True; s_agregado[(m_info['num'], s)] = True; d_agregado[(m_info['num'], s)] = True
                        locs_final.append({'nombre': l_name, 'celdas': celdas})
                    r_celdas_resumen = [{'active': r_agregado[(m_info['num'], s)]} for m_info in meses_info for s in m_info['semanas']]
                    ruts_final.append({'nombre': r_data['nombre'], 'ubicaciones': locs_final, 'celdas_resumen': r_celdas_resumen})
                f_celdas_resumen = [{'active': f_agregado[(m_info['num'], s)]} for m_info in meses_info for s in m_info['semanas']]
                frefs_final.append({'nombre': f_key_tuple[1], 'rutinas': ruts_final, 'celdas_resumen': f_celdas_resumen})
            s_celdas_resumen = [{'active': s_agregado[(m_info['num'], s)]} for m_info in meses_info for s in m_info['semanas']]
            subs_final.append({'nombre': s_nom, 'frecuencias': frefs_final, 'celdas_resumen': s_celdas_resumen})
        d_celdas_resumen = [{'active': d_agregado[(m_info['num'], s)]} for m_info in meses_info for s in m_info['semanas']]
        disciplinas_final.append({'nombre': d_nom, 'subs': subs_final, 'celdas_resumen': d_celdas_resumen})
    try:
        from core.models import ConfiguracionUI
        ui_config_obj = ConfiguracionUI.objects.first()
    except: ui_config_obj = None
    return render(request, 'mantenimiento/calendario_detallado.html', {
        'disciplinas': disciplinas_final, 'year': year, 'meses': meses_info, 'total_colspan': total_weeks + 1, 'ui_config': ui_config_obj
    })

@staff_member_required
def cronograma_mantenimiento_visual(request):
    from activos.models import Ubicacion
    year = int(request.GET.get('year', datetime.now().year))
    view_mode = request.GET.get('view_mode', 'sistema')
    ubicacion_id = request.GET.get('ubicacion_id')
    programacion_id = request.GET.get('programacion_id')
    ubicaciones_roots = Ubicacion.objects.filter(padre__isnull=True, tipo='EDIFICIO').order_by('nombre')
    filtros = {'inicio_programado__year': year}
    if programacion_id: filtros['programacion_id'] = programacion_id
    if ubicacion_id:
        try:
            area_sel = Ubicacion.objects.get(id=ubicacion_id)
            filtros['ubicacion_id__in'] = area_sel.get_descendants(include_self=True).values_list('id', flat=True)
        except: pass
    ordenes_list = list(OrdenTrabajo.objects.filter(**filtros).select_related('ubicacion', 'rutina__categoria', 'rutina__frecuencia', 'programacion__horario').values('id', 'rutina__nombre', 'ubicacion__nombre', 'ubicacion_id', 'rutina__categoria_id', 'inicio_programado', 'estado', 'programacion__horario__color', 'programacion_id'))
    existing_ot_keys = set((ot['programacion_id'], ot['inicio_programado'].date()) for ot in ordenes_list if ot.get('programacion_id'))
    proyecciones = Programacion.objects.filter(fecha_inicio__year__lte=year).select_related('rutina__categoria', 'rutina__frecuencia', 'horario')
    if programacion_id: proyecciones = proyecciones.filter(id=programacion_id)
    restricciones = set(RestriccionCalendario.objects.values_list('fecha', flat=True))
    for prog in proyecciones:
        fecha_ciclo = prog.fecha_inicio; limite = min(prog.fecha_fin or (prog.fecha_inicio + timedelta(days=365)), date(year, 12, 31))
        frec_dias = prog.rutina.frecuencia.dias; color = prog.horario.color if prog.horario else '#94a3b8'
        first_area = prog.areas.first(); ubi_nom = first_area.nombre if first_area else "Múltiples Áreas"; ubi_id = first_area.id if first_area else None
        while fecha_ciclo <= limite:
            if fecha_ciclo.year == year and (prog.id, fecha_ciclo) not in existing_ot_keys and fecha_ciclo not in restricciones:
                ordenes_list.append({'id': f'proj_{prog.id}_{fecha_ciclo}', 'rutina__nombre': prog.rutina.nombre, 'ubicacion__nombre': ubi_nom, 'ubicacion_id': ubi_id, 'rutina__categoria_id': prog.rutina.categoria_id, 'inicio_programado': datetime.combine(fecha_ciclo, datetime.min.time()), 'estado': 'PROYECCION', 'programacion__horario__color': color, 'programacion_id': prog.id})
            fecha_ciclo += timedelta(days=frec_dias)
    categorias = {c.id: c for c in Categoria.objects.all()}
    for c in categorias.values():
        if c.padre_id: c.padre = categorias.get(c.padre_id)
    grupos_dict = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list))))
    loc_map = {u.id: u for u in Ubicacion.objects.all()}
    def get_edificio_root(loc_id):
        curr = loc_map.get(loc_id)
        while curr:
            if curr.tipo == 'EDIFICIO': return curr
            curr = loc_map.get(curr.padre_id)
        return None
    for ot in ordenes_list:
        dia_año = ot['inicio_programado'].timetuple().tm_yday; semana_idx = min((dia_año - 1) // 7, 51)
        if view_mode == 'ubicacion':
            root_edificio = get_edificio_root(ot['ubicacion_id'])
            if not ubicacion_id and not root_edificio: continue
            group_label = root_edificio.nombre if root_edificio else (ot['ubicacion__nombre'] or "S/U")
            sub_label = "General" if root_edificio and (ot['ubicacion__nombre'] == root_edificio.nombre) else (ot['ubicacion__nombre'] or "General")
        else:
            cat_id = ot['rutina__categoria_id']
            if cat_id and cat_id in categorias:
                root = categorias[cat_id].get_root(); group_label = root.nombre; sub_label = categorias[cat_id].nombre if categorias[cat_id].id != root.id else "General"
            else: group_label = "General / Otros"; sub_label = "Sin Categoría"
        grupos_dict[group_label][sub_label][ot['rutina__nombre'] or "General"][semana_idx].append(ot)
    datos_finales = []; meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]; semanas = []
    base_date = datetime(year, 1, 1); base_date += timedelta(days=(7 - base_date.weekday())) if base_date.weekday() != 0 else timedelta(0)
    for i in range(52): semanas.append({'n': i + 1, 'inicio': base_date + timedelta(weeks=i), 'mes': meses_nombres[(base_date + timedelta(weeks=i)).month - 1]})
    for g_label, subs_map in sorted(grupos_dict.items()):
        celdas_grupo = []; best_color = '#3b82f6'; color_found = False
        for i in range(52):
            found_any = any(weeks_map.get(i, []) for s in subs_map.values() for r, weeks_map in s.items()); all_realizada = found_any and all(o['estado'] == 'REALIZADA' for s in subs_map.values() for r, weeks_map in s.items() for o in weeks_map.get(i, []))
            celdas_grupo.append({'active': found_any, 'realizada': all_realizada})
        subgrupos_nested = []
        for s_label, routines_map in sorted(subs_map.items()):
            celdas_sub = []
            for i in range(52):
                ots_in_sub = [o for r, w in routines_map.items() for o in w.get(i, [])]; any_in_week = len(ots_in_sub) > 0
                celdas_sub.append({'active': any_in_week, 'realizada': any_in_week and all(o['estado'] == 'REALIZADA' for o in ots_in_sub)})
            rutinas_nested = []
            for r_label, weeks_map in sorted(routines_map.items()):
                celdas_rutina = []; routine_color = '#3b82f6'
                for i in range(52):
                    ots = weeks_map.get(i, [])
                    if ots:
                        if not color_found: best_color = ots[0]['programacion__horario__color'] or '#3b82f6'; color_found = True
                        routine_color = ots[0]['programacion__horario__color'] or '#3b82f6'
                    first = ots[0] if ots else None
                    celdas_rutina.append({'active': bool(ots), 'realizada': bool(ots) and all(o['estado'] == 'REALIZADA' for o in ots), 'proyeccion': bool(ots) and all(o.get('estado') == 'PROYECCION' for o in ots), 'count': len(ots), 'info': ", ".join(set([str(o['rutina__nombre'] or 'S/R') if view_mode == 'ubicacion' else str(o['ubicacion__nombre'] or 'S/U') for o in ots])), 'prog_id': first.get('programacion_id') if first and first.get('estado') == 'PROYECCION' else None, 'date': first['inicio_programado'].date().isoformat() if first and first.get('estado') == 'PROYECCION' else None})
                rutinas_nested.append({'label': r_label, 'celdas': celdas_rutina, 'color': routine_color})
            subgrupos_nested.append({'label': s_label, 'celdas': celdas_sub, 'rutinas': rutinas_nested})
        datos_finales.append({'label': g_label, 'celdas': celdas_grupo, 'subgrupos': subgrupos_nested, 'color': best_color if color_found else '#3b82f6'})
    meses_header = [{'nombre': m, 'count': len([s for s in semanas if s['mes'] == m]), 'num': i + 1} for i, m in enumerate(meses_nombres) if any(s['mes'] == m for s in semanas)]
    current_ubi_id = int(ubicacion_id) if ubicacion_id else None
    for u in ubicaciones_roots: u.is_selected = (u.id == current_ubi_id)
    return render(request, 'mantenimiento/cronograma_fix.html', {'items': datos_finales, 'semanas': semanas, 'meses_header': meses_header, 'year': year, 'view_mode': view_mode, 'ubicaciones_roots': ubicaciones_roots, 'current_ubi': current_ubi_id, 'programacion_id': programacion_id})

@staff_member_required
def detalle_mes(request, year, month):
    import calendar
    programacion_id = request.GET.get('programacion_id')
    _, num_days = calendar.monthrange(year, month); days_range = range(1, num_days + 1); filtros = {'inicio_programado__year': year, 'inicio_programado__month': month}
    if programacion_id: filtros['programacion_id'] = programacion_id
    working_weekdays = set(range(7))
    if programacion_id:
        try:
            prog = Programacion.objects.get(id=programacion_id)
            if prog.horario: working_weekdays = set(prog.horario.dias.values_list('dia', flat=True))
        except: pass
    restricciones_mes = set(RestriccionCalendario.objects.filter(fecha__year=year, fecha__month=month).values_list('fecha__day', flat=True))
    non_working_days = [d for d in days_range if date(year, month, d).weekday() not in working_weekdays or d in restricciones_mes]
    ordenes = OrdenTrabajo.objects.filter(**filtros).select_related('rutina__categoria', 'rutina__frecuencia', 'ubicacion', 'programacion__horario').prefetch_related('activos', 'rutina__categoria')
    existing_ot_keys = set((ot.programacion_id, timezone.localtime(ot.inicio_programado).date()) for ot in ordenes if ot.programacion_id)
    month_start = date(year, month, 1); month_end = date(year, month, num_days); proyecciones_qs = Programacion.objects.filter(fecha_inicio__lte=month_end).select_related('rutina__categoria', 'rutina__frecuencia', 'horario')
    if programacion_id: proyecciones_qs = proyecciones_qs.filter(id=programacion_id)
    ghost_ots = []
    for prog in proyecciones_qs:
        limite = min(prog.fecha_fin or (prog.fecha_inicio + timedelta(days=365)), month_end); fecha_ciclo = prog.fecha_inicio; frec_dias = prog.rutina.frecuencia.dias
        if not frec_dias: continue
        if fecha_ciclo < month_start: fecha_ciclo += timedelta(days=((month_start - fecha_ciclo).days // frec_dias) * frec_dias)
        while fecha_ciclo <= limite:
            if fecha_ciclo >= month_start and (prog.id, fecha_ciclo) not in existing_ot_keys and fecha_ciclo.day not in restricciones_mes: ghost_ots.append({'prog': prog, 'fecha': fecha_ciclo})
            fecha_ciclo += timedelta(days=frec_dias)
    categs = {c.id: c for c in Categoria.objects.all()}
    for c in categs.values():
        if c.padre_id: c.padre = categs.get(c.padre_id)
    tree = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))))); system_colors = {}
    def add_to_tree_common(ot_dict, rut, ubi, assets, prog_color, day_key):
        cat = rut.categoria if rut else None
        if cat and cat.id in categs:
            fc = categs[cat.id]; root = fc.get_root(); sys_name = root.nombre; sub_name = fc.nombre if fc.id != root.id else "General"
            if sys_name not in system_colors: system_colors[sys_name] = prog_color or '#3b82f6'
        else: sys_name = "Sin Categoría"; sub_name = "General"; system_colors[sys_name] = '#64748b'
        tree[sys_name][sub_name][rut.nombre if rut else "OT Sin Rutina"][ubi.nombre if ubi else "Multiple"][(None, "General") if not assets else (assets[0].id, assets[0].nombre)][day_key].append(ot_dict)
    for ot in ordenes:
        sd = timezone.localtime(ot.inicio_programado); ed = timezone.localtime(ot.fin_programado or ot.inicio_programado); nc = max(1, math.ceil((ed - sd).total_seconds() / 86400))
        for i in range(nc):
            cd = sd.date() + timedelta(days=i)
            if cd.year == year and cd.month == month:
                dp = 'single' if nc == 1 else ('start' if i == 0 else ('end' if i == nc - 1 else 'middle'))
                info = {'id': ot.id, 'estado': ot.estado, 'inicio_iso': sd.strftime('%Y-%m-%d'), 'inicio_hm': sd.strftime('%H:%M'), 'fin_full': ed.strftime('%d/%m/%Y %H:%M'), 'fin_hm': ed.strftime('%H:%M'), 'rutina_nombre': ot.rutina.nombre if ot.rutina else "OT", 'activos_nombres': ", ".join([a.nombre for a in ot.activos.all()]), 'duration_pos': dp, 'color': ot.programacion.horario.color if ot.programacion and ot.programacion.horario else '#3b82f6'}
                add_to_tree_common(info, ot.rutina, ot.ubicacion, list(ot.activos.all()), info['color'], cd.day)
    for g in ghost_ots:
        p = g['prog']; f = g['fecha']; fa = p.areas.first()
        info = {'id': f'proj_{p.id}_{f}', 'estado': 'PROYECCION', 'inicio_iso': f.isoformat(), 'inicio_hm': '00:00', 'fin_full': '', 'fin_hm': '', 'rutina_nombre': p.rutina.nombre, 'activos_nombres': 'Simulado', 'duration_pos': 'single', 'prog_id': p.id, 'date': f.isoformat(), 'color': p.horario.color if p.horario else '#94a3b8'}
        add_to_tree_common(info, p.rutina, fa, [], info['color'], f.day)
    ft = []
    for sys in sorted(tree.keys()):
        subs = []; sda = collections.defaultdict(bool)
        for sub in sorted(tree[sys].keys()):
            ruts = []; subda = collections.defaultdict(bool)
            for rut in sorted(tree[sys][sub].keys()):
                ubis = []; rda = collections.defaultdict(bool)
                for ubi in sorted(tree[sys][sub][rut].keys()):
                    assets_l = []
                    for ak in sorted(tree[sys][sub][rut][ubi].keys(), key=lambda x: x[1]):
                        cells = []
                        for d in days_range:
                            ots = tree[sys][sub][rut][ubi][ak].get(d, []); hd = len(ots) > 0
                            cells.append({'day': d, 'ots': ots, 'active': hd})
                            if hd: rda[d] = True; subda[d] = True; sda[d] = True
                        assets_l.append({'label': ak[1], 'id': ak[0], 'celdas': cells})
                    ubis.append({'label': ubi, 'celdas': [{'day': d, 'active': any(a['celdas'][d-1]['active'] for a in assets_l)} for d in days_range], 'activos': assets_l})
                ruts.append({'label': rut, 'celdas': [{'day': d, 'active': rda[d]} for d in days_range], 'ubicaciones': ubis})
            subs.append({'label': sub, 'celdas': [{'day': d, 'active': subda[d]} for d in days_range], 'rutinas': ruts})
        ft.append({'label': sys, 'color': system_colors.get(sys, "#64748b"), 'celdas': [{'day': d, 'active': sda[d]} for d in days_range], 'subs': subs})
    return render(request, 'mantenimiento/detalle_mes.html', {'year': year, 'month': month, 'mes_nombre': ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][month], 'days_range': days_range, 'tree': ft, 'programacion_id': programacion_id, 'non_working_days': non_working_days})

@staff_member_required
def visualizador_proyecciones(request, pk):
    prog = get_object_or_404(Programacion, pk=pk); fechas = []; fc = prog.fecha_inicio; lim = prog.fecha_fin or (prog.fecha_inicio + timedelta(days=365)); fd = prog.rutina.frecuencia.dias; restr = set(RestriccionCalendario.objects.values_list('fecha', flat=True))
    while fc <= lim:
        fechas.append({'fecha': fc, 'es_festivo': fc in restr, 'es_fin_semana': fc.weekday() >= 5, 'dias_frecuencia': fd}); fc += timedelta(days=fd)
    return render(request, 'mantenimiento/visualizador_proyecciones.html', {'prog': prog, 'fechas': fechas})
