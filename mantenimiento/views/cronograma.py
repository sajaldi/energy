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

def to_int(value, default=None):
    if value is None: return default
    try:
        # Limpiar posibles caracteres de formato como espacios de no ruptura (\xa0) o espacios normales
        clean_val = str(value).replace('\xa0', '').replace(' ', '').replace(',', '')
        if not clean_val: return default
        return int(clean_val)
    except (ValueError, TypeError):
        return default

@staff_member_required
def calendario_mantenimiento(request):
    from ..services import WorkOrderService
    year = to_int(request.GET.get('year'), date.today().year)
    
    # 1. Obtener la estructura agrupada desde el servicio
    tree = WorkOrderService.get_grouped_tree(year)
    
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

    # 2. Helpers para el resumen de celdas
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

    # 3. Construir la estructura final para el template
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
    from ..services import WorkOrderService
    year = to_int(request.GET.get('year'), date.today().year)
    
    # 1. Obtener la estructura detallada desde el servicio
    tree = WorkOrderService.get_detailed_tree(year)

    MESES_NOMBRES = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
    meses_info = []
    total_weeks = 0
    for i, nombre in enumerate(MESES_NOMBRES):
        m_num = i + 1
        days_in_month = calendar.monthrange(year, m_num)[1]
        num_weeks = (days_in_month - 1) // 7 + 1
        meses_info.append({'nombre': nombre, 'num': m_num, 'semanas': list(range(1, num_weeks + 1))})
        total_weeks += num_weeks

    # 2. Construir la estructura final para el template
    disciplinas_final = []
    for d_nom in sorted(tree.keys()):
        subs_final = []
        for s_nom in sorted(tree[d_nom].keys()):
            frefs_final = []
            for f_key_tuple in sorted(tree[d_nom][s_nom].keys()):
                ruts_final = []
                for r_id in sorted(tree[d_nom][s_nom][f_key_tuple].keys()):
                    r_data = tree[d_nom][s_nom][f_key_tuple][r_id]
                    ubicaciones_list = []
                    for loc_name in sorted(r_data['ubicaciones'].keys()):
                        loc_data = r_data['ubicaciones'][loc_name]
                        celdas = []
                        for m_info in meses_info:
                            for s in m_info['semanas']:
                                key = (m_info['num'], s)
                                celdas.append({
                                    'active': loc_data['matrix'][key],
                                    'orders': loc_data['orders'][key]
                                })
                        ubicaciones_list.append({'nombre': loc_name, 'celdas': celdas})
                    ruts_final.append({'nombre': r_data['nombre'], 'ubicaciones': ubicaciones_list})
                frefs_final.append({'nombre': f_key_tuple[1], 'rutinas': ruts_final})
            subs_final.append({'nombre': s_nom, 'frecuencias': frefs_final})
        disciplinas_final.append({'nombre': d_nom, 'subs': subs_final})

    return render(request, 'mantenimiento/calendario_detallado.html', {
        'disciplinas': disciplinas_final, 'year': year, 'meses': meses_info, 'total_colspan': total_weeks + 2
    })

@staff_member_required
def cronograma_mantenimiento_visual(request):
    from ..services import WorkOrderService
    year = to_int(request.GET.get('year'), datetime.now().year)
    view_mode = request.GET.get('view_mode', 'sistema')
    
    def parse_ids(param):
        val = request.GET.getlist(param)
        if not val:
            val = request.GET.get(param, '')
            if ',' in val: 
                return [to_int(x) for x in val.split(',') if to_int(x) is not None]
            parsed = to_int(val)
            return [parsed] if parsed is not None else []
        return [to_int(x) for x in val if to_int(x) is not None]

    ubicacion_ids = parse_ids('ubicacion_id')
    categoria_ids = parse_ids('categoria_id')
    programacion_id = request.GET.get('programacion_id')

    # Usar el servicio para obtener los datos base
    data = WorkOrderService.get_calendar_data(
        year=year,
        view_mode=view_mode,
        ubicacion_ids=ubicacion_ids,
        categoria_ids=categoria_ids,
        programacion_id=programacion_id
    )
    
    grupos_dict = data['grupos_dict']
    semanas = data['semanas']
    meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    
    datos_finales = []
    for g_label, subs_map in sorted(grupos_dict.items()):
        celdas_grupo = []
        best_color = '#3b82f6'
        color_found = False
        
        for i in range(52):
            found_any = any(weeks_map.get(i, []) for s in subs_map.values() for r, weeks_map in s.items())
            all_realizada = found_any and all(o['estado'] == 'REALIZADA' for s in subs_map.values() for r, weeks_map in s.items() for o in weeks_map.get(i, []))
            celdas_grupo.append({'active': found_any, 'realizada': all_realizada})
            
        subgrupos_nested = []
        for s_label, routines_map in sorted(subs_map.items()):
            celdas_sub = []
            for i in range(52):
                ots_in_sub = [o for r, w in routines_map.items() for o in w.get(i, [])]
                any_in_week = len(ots_in_sub) > 0
                celdas_sub.append({'active': any_in_week, 'realizada': any_in_week and all(o['estado'] == 'REALIZADA' for o in ots_in_sub)})
                
            rutinas_nested = []
            for r_label, weeks_map in sorted(routines_map.items()):
                celdas_rutina = []
                routine_color = '#3b82f6'
                for i in range(52):
                    ots = weeks_map.get(i, [])
                    if ots:
                        if not color_found: 
                            best_color = ots[0]['programacion__horario__color'] or '#3b82f6'
                            color_found = True
                        routine_color = ots[0]['programacion__horario__color'] or '#3b82f6'
                    
                    first = ots[0] if ots else None
                    celdas_rutina.append({
                        'active': bool(ots), 
                        'realizada': bool(ots) and all(o['estado'] == 'REALIZADA' for o in ots), 
                        'proyeccion': bool(ots) and all(o.get('estado') == 'PROYECCION' for o in ots), 
                        'count': len(ots), 
                        'info': ", ".join(set([str(o['rutina__nombre'] or 'S/R') if view_mode == 'ubicacion' else str(o['ubicacion__nombre'] or 'S/U') for o in ots])), 
                        'prog_id': first.get('programacion_id') if first and first.get('estado') == 'PROYECCION' else None, 
                        'date': first['inicio_programado'].date().isoformat() if first and first.get('estado') == 'PROYECCION' else None
                    })
                rutinas_nested.append({'label': r_label, 'celdas': celdas_rutina, 'color': routine_color})
            subgrupos_nested.append({'label': s_label, 'celdas': celdas_sub, 'rutinas': rutinas_nested})
        datos_finales.append({'label': g_label, 'celdas': celdas_grupo, 'subgrupos': subgrupos_nested, 'color': best_color if color_found else '#3b82f6'})
        
    meses_header = [{'nombre': m, 'count': len([s for s in semanas if s['mes'] == m]), 'num': i + 1} for i, m in enumerate(meses_nombres) if any(s['mes'] == m for s in semanas)]
    
    from activos.models import Ubicacion
    ubicaciones_roots = Ubicacion.objects.filter(padre__isnull=True, tipo='EDIFICIO').order_by('nombre')
    first_ubi_id = ubicacion_ids[0] if ubicacion_ids else None
    for u in ubicaciones_roots: 
        u.is_selected = (u.id == first_ubi_id)
        
    return render(request, 'mantenimiento/cronograma_fix.html', {
        'items': datos_finales, 'semanas': semanas, 'meses_header': meses_header, 
        'year': year, 'view_mode': view_mode, 'ubicaciones_roots': ubicaciones_roots, 
        'current_ubi': first_ubi_id, 'programacion_id': programacion_id
    })

@staff_member_required
def wizard_cronograma(request):
    """Interfaz visual para filtrar el cronograma."""
    from activos.models import Ubicacion
    from ..models import Categoria
    from django.shortcuts import redirect
    from django.urls import reverse
    
    year = to_int(request.GET.get('year'), datetime.now().year)
    view_type = request.GET.get('view_type', 'anual')
    month = to_int(request.GET.get('month'))
    
    # Si se envía el formulario con view_type, redirigir a la vista apropiada
    if view_type == 'mensual' and month:
        # Redirigir a la vista mensual (detalle_mes)
        params = request.GET.copy()
        # Remover parámetros que no se usan en detalle_mes
        params.pop('view_type', None)
        params.pop('month', None)
        return redirect(f"{reverse('mantenimiento:detalle_mes', kwargs={'year': year, 'month': month})}?{params.urlencode()}")
    elif 'view_type' in request.GET:
        # Redirigir a la vista anual (cronograma principal)
        params = request.GET.copy()
        params.pop('view_type', None)
        params.pop('month', None)
        return redirect(f"{reverse('mantenimiento:cronograma')}?{params.urlencode()}")
    
    # Mostrar el wizard (GET sin view_type)
    ubicaciones_roots = Ubicacion.objects.filter(padre=None).prefetch_related('sub_ubicaciones')
    categorias_roots = Categoria.objects.filter(padre=None).prefetch_related('subcategorias')
    
    return render(request, 'mantenimiento/wizard_cronograma.html', {
        'year': year,
        'ubicaciones': ubicaciones_roots,
        'categorias': categorias_roots
    })

@staff_member_required
def detalle_mes(request, year, month):
    from ..services import WorkOrderService
    import calendar
    from django.core.cache import cache
    import hashlib
    import json
    
    programacion_id = request.GET.get('programacion_id')
    view_mode = request.GET.get('view_mode', 'sistema')
    filter_q = request.GET.get('filter_q')
    
    # Crear cache key basado en parámetros
    cache_params = {
        'year': year,
        'month': month,
        'view_mode': view_mode,
        'programacion_id': programacion_id,
        'filter_q': filter_q,
        # No incluir ubicacion_id ni categoria_id en cache para evitar cache bloat
    }
    cache_key = f"detalle_mes_{hashlib.md5(json.dumps(cache_params, sort_keys=True).encode()).hexdigest()}"
    
    # Intentar obtener del cache (15 minutos)
    cached_data = cache.get(cache_key)
    if cached_data and not request.GET.get('nocache'):
        return render(request, 'mantenimiento/detalle_mes.html', cached_data)
    
    _, num_days = calendar.monthrange(year, month)
    days_range = range(1, num_days + 1)
    
    # Calcular días no laborables y restricciones
    working_weekdays = set(range(7))
    if programacion_id:
        try:
            prog = Programacion.objects.get(id=programacion_id)
            if prog.horario: working_weekdays = set(prog.horario.dias.values_list('dia', flat=True))
        except: pass
        
    restricciones_mes = set(RestriccionCalendario.objects.filter(fecha__year=year, fecha__month=month).values_list('fecha__day', flat=True))
    non_working_days = [d for d in days_range if date(year, month, d).weekday() not in working_weekdays or d in restricciones_mes]

    # Get Data from Service based on View Mode
    if view_mode == 'ubicacion':
        tree = WorkOrderService.get_location_grouped_tree(year, month)
    else:
        # Legacy Logic for 'sistema' view - OPTIMIZED with select_related/prefetch_related
        filtros = {'inicio_programado__year': year, 'inicio_programado__month': month}
        if programacion_id: filtros['programacion_id'] = programacion_id
        
        # BRUTAL OPTIMIZATION: Single optimized query instead of N+1
        ordenes = OrdenTrabajo.objects.filter(**filtros).select_related(
            'rutina',
            'rutina__categoria',
            'rutina__categoria__padre',
            'rutina__frecuencia',
            'ubicacion',
            'programacion',
            'programacion__horario'
        ).prefetch_related('activos')
        
        existing_ot_keys = set((ot.programacion_id, timezone.localtime(ot.inicio_programado).date()) for ot in ordenes if ot.programacion_id)
        
        month_start = date(year, month, 1)
        month_end = date(year, month, num_days)
        
        proyecciones_qs = Programacion.objects.filter(fecha_inicio__lte=month_end).select_related('rutina__categoria', 'rutina__frecuencia', 'horario')
        if programacion_id: proyecciones_qs = proyecciones_qs.filter(id=programacion_id)
        
        ghost_ots = []
        working_days_cache = {}

        for prog in proyecciones_qs:
            limite = min(prog.fecha_fin or (prog.fecha_inicio + timedelta(days=365)), month_end)
            fecha_ciclo = prog.fecha_inicio
            frec_dias = prog.rutina.frecuencia.dias
            if not frec_dias: continue
            
            if prog.horario_id not in working_days_cache:
                working_days_cache[prog.horario_id] = set(prog.horario.dias.values_list('dia', flat=True)) if prog.horario else set(range(7))
            working_days = working_days_cache[prog.horario_id]
            
            if fecha_ciclo < month_start: 
                fecha_ciclo += timedelta(days=max(0, (month_start - fecha_ciclo).days // frec_dias) * frec_dias)
            
            while fecha_ciclo <= limite:
                fecha_proyectada = fecha_ciclo
                while fecha_proyectada <= limite and (fecha_proyectada in restricciones_mes or fecha_proyectada.weekday() not in working_days):
                    fecha_proyectada += timedelta(days=1)
                    
                if fecha_proyectada >= month_start and fecha_proyectada <= limite and (prog.id, fecha_proyectada) not in existing_ot_keys and fecha_proyectada.day not in restricciones_mes: 
                    ghost_ots.append({'prog': prog, 'fecha': fecha_proyectada})
                fecha_ciclo += timedelta(days=frec_dias)

        categs = {c.id: c for c in Categoria.objects.all()}
        for c in categs.values():
            if c.padre_id: c.padre = categs.get(c.padre_id)
            
        # Structure: Tree[Sys][Sub][Rut][Ubi][AssetKey][Day] -> List of OTs
        tree_dict = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list))))))
        system_colors = {}

        def add_to_tree_common(ot_dict, rut, ubi, assets, prog_color, day_key):
            cat = rut.categoria if rut else None
            if cat and cat.id in categs:
                fc = categs[cat.id]
                root = fc.get_root()
                sys_name = root.nombre
                sub_name = fc.nombre if fc.id != root.id else "General"
                if sys_name not in system_colors: system_colors[sys_name] = prog_color or '#3b82f6'
            else: 
                sys_name = "Sin Categoría"
                sub_name = "General"
                system_colors[sys_name] = '#64748b'
            
            asset_key = (assets[0].id, assets[0].nombre) if assets else (None, "General")
            rut_key = (rut.nombre, rut.frecuencia.nombre) if rut and rut.frecuencia else (rut.nombre if rut else "OT Sin Rutina", "")
            tree_dict[sys_name][sub_name][rut_key][ubi.nombre if ubi else "Multiple"][asset_key][day_key].append(ot_dict)

        for ot in ordenes:
            sd = timezone.localtime(ot.inicio_programado)
            ed = timezone.localtime(ot.fin_programado or ot.inicio_programado)
            nc = max(1, math.ceil((ed - sd).total_seconds() / 86400))
            assets = list(ot.activos.all())
            
            for i in range(nc):
                cd = sd.date() + timedelta(days=i)
                if cd.year == year and cd.month == month:
                    dp = 'single' if nc == 1 else ('start' if i == 0 else ('end' if i == nc - 1 else 'middle'))
                    base_info = {
                        'id': ot.id, 'estado': ot.estado, 
                        'inicio_iso': sd.strftime('%Y-%m-%d'), 'inicio_hm': sd.strftime('%H:%M'), 
                        'fin_full': ed.strftime('%d/%m/%Y %H:%M'), 'fin_hm': ed.strftime('%H:%M'), 
                        'rutina_nombre': ot.rutina.nombre if ot.rutina else "OT", 
                        'activos_nombres': ", ".join([a.nombre for a in assets]), 
                        'duration_pos': dp, 
                        'color': ot.programacion.horario.color if ot.programacion and ot.programacion.horario else '#3b82f6'
                    }
                    
                    if not assets:
                        add_to_tree_common(base_info, ot.rutina, ot.ubicacion, [], base_info['color'], cd.day)
                    else:
                        for idx, a in enumerate(assets):
                            info = base_info.copy()
                            if len(assets) > 1:
                                info['group_type'] = 'start' if idx == 0 else ('end' if idx == len(assets) - 1 else 'middle')
                            add_to_tree_common(info, ot.rutina, ot.ubicacion, [a], base_info['color'], cd.day)

        for g in ghost_ots:
            p = g['prog']; f = g['fecha']; fa = p.areas.first()
            info = {
                'id': f'proj_{p.id}_{f}', 'estado': 'PROYECCION', 
                'inicio_iso': f.isoformat(), 'inicio_hm': '00:00', 
                'fin_full': '', 'fin_hm': '', 
                'rutina_nombre': p.rutina.nombre, 'activos_nombres': 'Simulado', 
                'duration_pos': 'single', 'prog_id': p.id, 'date': f.isoformat(), 
                'color': p.horario.color if p.horario else '#94a3b8'
            }
            add_to_tree_common(info, p.rutina, fa, [], info['color'], f.day)

        # Convert to list structure
        tree = []
        for sys in sorted(tree_dict.keys()):
            subs = []; sda = collections.defaultdict(bool)
            for sub in sorted(tree_dict[sys].keys()):
                ruts = []; subda = collections.defaultdict(bool)
                for rut_key in sorted(tree_dict[sys][sub].keys()):
                    ubis = []; rda = collections.defaultdict(bool)
                    for ubi in sorted(tree_dict[sys][sub][rut_key].keys()):
                        assets_l = []
                        for ak in sorted(tree_dict[sys][sub][rut_key][ubi].keys(), key=lambda x: x[1]):
                            cells = []
                            for d in days_range:
                                ots = tree_dict[sys][sub][rut_key][ubi][ak].get(d, [])
                                active = len(ots) > 0
                                gt = ots[0].get('group_type') if ots else None
                                cells.append({'day': d, 'ots': ots, 'active': active, 'group_type': gt})
                                if active: rda[d] = True; subda[d] = True; sda[d] = True
                            assets_l.append({'label': ak[1], 'id': ak[0], 'celdas': cells})
                        ubis.append({'label': ubi, 'celdas': [{'day': d, 'active': any(a['celdas'][d-1]['active'] for a in assets_l)} for d in days_range], 'activos': assets_l})
                    ruts.append({'label': rut_key[0], 'frecuencia': rut_key[1], 'celdas': [{'day': d, 'active': rda[d]} for d in days_range], 'ubicaciones': ubis})
                subs.append({'label': sub, 'celdas': [{'day': d, 'active': subda[d]} for d in days_range], 'rutinas': ruts})
            tree.append({'label': sys, 'color': system_colors.get(sys, "#64748b"), 'celdas': [{'day': d, 'active': sda[d]} for d in days_range], 'subs': subs})
    
    
    # REVERTING STRATEGY: I will ONLY add the if view_mode == 'ubicacion' block and keep the rest as 'else'.
    # This minimizes checking changes.
    
    # --- Filtering Logic ---
    filter_options = sorted([t['label'] for t in tree])
    filter_q = request.GET.get('filter_q')
    
    if filter_q and filter_q != 'TODOS':
        tree = [t for t in tree if t['label'] == filter_q]

    # Prepare context
    context = {
        'year': year, 'month': month, 
        'mes_nombre': ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][month], 
        'days_range': days_range, 
        'tree': tree, 
        'programacion_id': programacion_id, 
        'non_working_days': non_working_days,
        'view_mode': view_mode,
        'filter_options': filter_options,
        'current_filter': filter_q
    }
    
    # BRUTAL OPTIMIZATION: Cache result for 15 minutes
    cache.set(cache_key, context, 60 * 15)

    return render(request, 'mantenimiento/detalle_mes.html', context)

@staff_member_required
def visualizador_proyecciones(request, pk):
    prog = get_object_or_404(Programacion, pk=pk); fechas = []; fc = prog.fecha_inicio; lim = prog.fecha_fin or (prog.fecha_inicio + timedelta(days=365)); fd = prog.rutina.frecuencia.dias; restr = set(RestriccionCalendario.objects.values_list('fecha', flat=True))
    while fc <= lim:
        fechas.append({'fecha': fc, 'es_festivo': fc in restr, 'es_fin_semana': fc.weekday() >= 5, 'dias_frecuencia': fd}); fc += timedelta(days=fd)
    return render(request, 'mantenimiento/visualizador_proyecciones.html', {'prog': prog, 'fechas': fechas})
