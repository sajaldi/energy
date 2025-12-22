
from django.shortcuts import render
from django.http import JsonResponse
from .models import OrdenTrabajo, Rutina, Categoria
from datetime import date, timedelta
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
        'programacion__horario__dias'
    ).order_by(
        'rutina__categoria__nombre',
        'rutina__nombre',
        'inicio_programado'
    )
    
    MESES_NOMBRES = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
    
    meses_info = []
    total_weeks = 0
    for i, nombre in enumerate(MESES_NOMBRES):
        m_num = i + 1
        days_in_month = calendar.monthrange(year, m_num)[1]
        num_weeks = 5 if days_in_month > 28 else 4
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
                'horario_compelto': horario_obj.resumen_corto() if horario_obj else "N/A",
                'matrix': collections.defaultdict(list)
            }
        
        mes = ot.inicio_programado.month
        dia = ot.inicio_programado.day
        semana = (dia - 1) // 7 + 1
        
        # Guardar info de la orden para el popup
        order_info = {
            'id': ot.id,
            'ubicacion': ot.ubicacion.nombre if ot.ubicacion else "S/A",
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

    # Convertir a listas ordenadas para el template
    disciplinas_final = []
    for d_nom in sorted(tree.keys()):
        subs_final = []
        for s_nom in sorted(tree[d_nom].keys()):
            frefs_final = []
            # Sort frequencies by the first element of the tuple (dias_entre_mantenimiento)
            for f_key_tuple in sorted(tree[d_nom][s_nom].keys()):
                f_display_name = f_key_tuple[1] # Get the actual frequency name from the tuple
                ruts_final = []
                for r_id in sorted(tree[d_nom][s_nom][f_key_tuple].keys()):
                    r_data = tree[d_nom][s_nom][f_key_tuple][r_id]
                    celdas = []
                    for m_info in meses_info:
                        for s in m_info['semanas']:
                            celdas.append(group_locations(r_data['matrix'][(m_info['num'], s)]))
                    ruts_final.append({
                        'nombre': r_data['nombre'],
                        'descripcion': r_data['descripcion'],
                        'horario': r_data['horario_compelto'],
                        'celdas': celdas
                    })
                frefs_final.append({
                    'nombre': f_display_name,
                    'rutinas': ruts_final
                })
            subs_final.append({
                'nombre': s_nom,
                'frecuencias': frefs_final
            })
        disciplinas_final.append({
            'nombre': d_nom,
            'subs': subs_final
        })

    return render(request, 'mantenimiento/calendario.html', {
        'disciplinas': disciplinas_final,
        'year': year,
        'meses': meses_info,
        'total_colspan': total_weeks + 2
    })


