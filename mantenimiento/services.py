import collections
import calendar
import math
from datetime import datetime, date, timedelta
from django.db.models import Q, Count
from django.utils import timezone
from .models import OrdenTrabajo, Rutina, Categoria, Programacion, RestriccionCalendario

class WorkOrderService:
    @staticmethod
    def get_calendar_data(year, view_mode='sistema', ubicacion_id=None, programacion_id=None):
        """
        Logic for grouping and projecting Work Orders for the visual calendar.
        Refactored from cronograma_mantenimiento_visual.
        """
        from activos.models import Ubicacion, Activo
        
        filtros = {'inicio_programado__year': year}
        if programacion_id:
            filtros['programacion_id'] = programacion_id
            
        if ubicacion_id:
            try:
                area_sel = Ubicacion.objects.get(id=ubicacion_id)
                filtros['ubicacion_id__in'] = area_sel.get_descendants(include_self=True).values_list('id', flat=True)
            except Ubicacion.DoesNotExist:
                pass
        
        # 1. Fetch real Work Orders
        ordenes_qs = OrdenTrabajo.objects.filter(**filtros).select_related(
            'ubicacion', 'rutina__categoria', 'rutina__frecuencia', 'programacion__horario'
        ).values(
            'id', 'rutina__nombre', 'ubicacion__nombre', 'ubicacion_id', 
            'rutina__categoria_id', 'inicio_programado', 'estado', 
            'programacion__horario__color', 'programacion_id'
        )
        
        ordenes_list = list(ordenes_qs)
        existing_ot_keys = set((ot['programacion_id'], ot['inicio_programado'].date()) for ot in ordenes_list if ot.get('programacion_id'))
        
        # 2. Handle Projections (Ghost OTs)
        proyecciones = Programacion.objects.filter(fecha_inicio__year__lte=year).select_related(
            'rutina__categoria', 'rutina__frecuencia', 'horario'
        )
        if programacion_id:
            proyecciones = proyecciones.filter(id=programacion_id)
            
        restricciones = set(RestriccionCalendario.objects.values_list('fecha', flat=True))
        working_days_cache = {}
        
        for prog in proyecciones:
            fecha_ciclo = prog.fecha_inicio
            limite = min(prog.fecha_fin or (prog.fecha_inicio + timedelta(days=365)), date(year, 12, 31))
            frec_dias = prog.rutina.frecuencia.dias
            color = prog.horario.color if prog.horario else '#94a3b8'
            
            if prog.horario_id not in working_days_cache:
                working_days_cache[prog.horario_id] = set(prog.horario.dias.values_list('dia', flat=True)) if prog.horario else set(range(7))
            working_days = working_days_cache[prog.horario_id]

            # Simplified projection logic for the service
            first_area = prog.areas.first()
            ubi_nom = first_area.nombre if first_area else "Múltiples Áreas"
            ubi_id = first_area.id if first_area else None
            
            while fecha_ciclo <= limite:
                fecha_proyectada = fecha_ciclo
                # Find next available working day
                while fecha_proyectada <= limite and (fecha_proyectada in restricciones or fecha_proyectada.weekday() not in working_days):
                    fecha_proyectada += timedelta(days=1)
                
                if fecha_proyectada.year == year and (prog.id, fecha_proyectada) not in existing_ot_keys and fecha_proyectada not in restricciones:
                    ordenes_list.append({
                        'id': f'proj_{prog.id}_{fecha_proyectada}',
                        'rutina__nombre': prog.rutina.nombre,
                        'ubicacion__nombre': ubi_nom,
                        'ubicacion_id': ubi_id,
                        'rutina__categoria_id': prog.rutina.categoria_id,
                        'inicio_programado': datetime.combine(fecha_proyectada, datetime.min.time()),
                        'estado': 'PROYECCION',
                        'programacion__horario__color': color,
                        'programacion_id': prog.id
                    })
                
                fecha_ciclo += timedelta(days=frec_dias)

        # 3. Grouping logic
        categorias = {c.id: c for c in Categoria.objects.all()}
        for c in categorias.values():
            if c.padre_id: c.padre = categorias.get(c.padre_id)
            
        loc_map = {u.id: u for u in Ubicacion.objects.all()}
        
        def get_edificio_root(loc_id):
            curr = loc_map.get(loc_id)
            while curr:
                if curr.tipo == 'EDIFICIO': return curr
                curr = loc_map.get(curr.padre_id)
            return None

        grupos_dict = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list))))
        
        for ot in ordenes_list:
            # Determine grouping week (0-51)
            dia_año = ot['inicio_programado'].timetuple().tm_yday
            semana_idx = min((dia_año - 1) // 7, 51)
            
            if view_mode == 'ubicacion':
                root_edificio = get_edificio_root(ot['ubicacion_id'])
                if not ubicacion_id and not root_edificio: continue
                group_label = root_edificio.nombre if root_edificio else (ot['ubicacion__nombre'] or "S/U")
                sub_label = "General" if root_edificio and (ot['ubicacion__nombre'] == root_edificio.nombre) else (ot['ubicacion__nombre'] or "General")
            else:
                cat_id = ot['rutina__categoria_id']
                if cat_id and cat_id in categorias:
                    root = categorias[cat_id].get_root()
                    group_label = root.nombre
                    sub_label = categorias[cat_id].nombre if categorias[cat_id].id != root.id else "General"
                else:
                    group_label = "General / Otros"
                    sub_label = "Sin Categoría"
                    
            grupos_dict[group_label][sub_label][ot['rutina__nombre'] or "General"][semana_idx].append(ot)
            
        return {
            'grupos_dict': grupos_dict,
            'year': year,
            'semanas': WorkOrderService._generate_weeks_metadata(year)
        }

    @staticmethod
    def get_grouped_tree(year):
        """Logic for grouping orders by Category > Subcategory > Frequency > Routine"""
        ordenes = OrdenTrabajo.objects.filter(inicio_programado__year=year).select_related(
            'rutina__categoria', 'rutina__frecuencia', 'ubicacion', 'programacion__horario'
        ).prefetch_related('programacion__horario__dias', 'activos').order_by(
            'rutina__categoria__nombre', 'rutina__nombre', 'inicio_programado'
        )
        
        categorias_full = {c.id: c for c in Categoria.objects.all()}
        for cat in categorias_full.values():
            if cat.padre_id:
                cat.padre = categorias_full.get(cat.padre_id)

        tree = {}
        for ot in ordenes:
            rut = ot.rutina
            cat = rut.categoria if rut else None
            
            if cat:
                if cat.id in categorias_full:
                    cat = categorias_full[cat.id]
                dis_name = cat.get_root().nombre
                sub_name = cat.nombre
            else:
                dis_name = "SIN CATEGORÍA"
                sub_name = "GENERAL"
                
            frec = rut.frecuencia if rut else None
            f_key = (frec.dias, frec.nombre) if frec and frec.dias is not None else (float('inf'), "SIN FRECUENCIA")
            r_key = rut.id if rut else 0

            if dis_name not in tree: tree[dis_name] = {}
            if sub_name not in tree[dis_name]: tree[dis_name][sub_name] = {}
            if f_key not in tree[dis_name][sub_name]: tree[dis_name][sub_name][f_key] = {}
            if r_key not in tree[dis_name][sub_name][f_key]:
                horario_obj = ot.programacion.horario if ot.programacion else None
                tree[dis_name][sub_name][f_key][r_key] = {
                    'nombre': rut.nombre if rut else "OT",
                    'descripcion': (rut.descripcion if rut else "") or "Sin descripción",
                    'horario_nombre': horario_obj.nombre if horario_obj else "N/A",
                    'horario_completo': horario_obj.resumen_corto() if horario_obj else "N/A",
                    'matrix': collections.defaultdict(list)
                }
            
            mes = ot.inicio_programado.month
            dia = ot.inicio_programado.day
            semana = (dia - 1) // 7 + 1
            
            tree[dis_name][sub_name][f_key][r_key]['matrix'][(mes, semana)].append({
                'id': ot.id,
                'ubicacion': ot.ubicacion.nombre if ot.ubicacion else "S/A",
                'activos': [a.nombre for a in ot.activos.all()],
                'inicio': ot.inicio_programado.strftime('%H:%M'),
                'fin': ot.fin_programado.strftime('%H:%M'),
                'fecha': ot.inicio_programado.strftime('%d/%m/%Y'),
                'estado': ot.estado
            })
        return tree

    @staticmethod
    def get_detailed_tree(year):
        """Logic for grouping orders by Category > Routine > Ubicacion"""
        ordenes = OrdenTrabajo.objects.filter(inicio_programado__year=year).select_related(
            'rutina__categoria', 'rutina__frecuencia', 'ubicacion'
        ).order_by('rutina__categoria__nombre', 'rutina__nombre', 'ubicacion__nombre', 'inicio_programado')
        
        categorias_full = {c.id: c for c in Categoria.objects.all()}
        for cat in categorias_full.values():
            if cat.padre_id: cat.padre = categorias_full.get(cat.padre_id)

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
            
            f_key = (rut.frecuencia.dias, rut.frecuencia.nombre) if rut.frecuencia else (float('inf'), "SIN FRECUENCIA")
            r_key = rut.id
            loc_name = ot.ubicacion.nombre if ot.ubicacion else "S/A"
            
            if dis_name not in tree: tree[dis_name] = {}
            if sub_name not in tree[dis_name]: tree[dis_name][sub_name] = {}
            if f_key not in tree[dis_name][sub_name]: tree[dis_name][sub_name][f_key] = {}
            if r_key not in tree[dis_name][sub_name][f_key]: 
                tree[dis_name][sub_name][f_key][r_key] = {'nombre': rut.nombre, 'ubicaciones': {}}
            if loc_name not in tree[dis_name][sub_name][f_key][r_key]['ubicaciones']:
                tree[dis_name][sub_name][f_key][r_key]['ubicaciones'][loc_name] = {
                    'matrix': collections.defaultdict(bool), 
                    'orders': collections.defaultdict(list)
                }
            
            mes = ot.inicio_programado.month; dia = ot.inicio_programado.day; semana = (dia - 1) // 7 + 1
            tree[dis_name][sub_name][f_key][r_key]['ubicaciones'][loc_name]['matrix'][(mes, semana)] = True
            tree[dis_name][sub_name][f_key][r_key]['ubicaciones'][loc_name]['orders'][(mes, semana)].append({
                'id': ot.id, 'inicio': ot.inicio_programado.strftime('%H:%M'), 
                'fin': ot.fin_programado.strftime('%H:%M'), 'fecha': ot.inicio_programado.strftime('%d/%m/%Y'), 'estado': ot.estado
            })
        return tree
