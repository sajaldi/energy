import collections
import calendar
import math
from datetime import datetime, date, timedelta
from django.db.models import Q, Count, Subquery, OuterRef
from django.utils import timezone
from .models import OrdenTrabajo, Rutina, Tipo, Programacion, RestriccionCalendario, ArchivoOrdenTrabajo, Horario
from django.conf import settings
from django.core.files.base import ContentFile
from .utils.pdf_utils import generate_ot_pdf_bytes

class WorkOrderService:
    @staticmethod
    def get_calendar_data(year, view_mode='sistema', ubicacion_ids=None, tipo_ids=None, programacion_id=None, rutina_id=None):
        """
        Logic for grouping and projecting Work Orders for the visual calendar.
        Refactored from cronograma_mantenimiento_visual.
        """
        from activos.models import Ubicacion, Activo
        
        filtros = {'inicio_programado__year': year}
        if programacion_id:
            filtros['programacion_id'] = programacion_id

        if rutina_id:
            filtros['rutina_id'] = rutina_id
            
        if ubicacion_ids:
            if isinstance(ubicacion_ids, str): ubicacion_ids = [int(x) for x in ubicacion_ids.split(',') if x.strip()]
            all_ids = set()
            for uid in ubicacion_ids:
                try:
                    area = Ubicacion.objects.get(id=uid)
                    all_ids.update(area.get_descendants(include_self=True).values_list('id', flat=True))
                except Ubicacion.DoesNotExist: pass
            filtros['ubicacion_id__in'] = list(all_ids)
            
        if tipo_ids:
            if isinstance(tipo_ids, str): tipo_ids = [int(x) for x in tipo_ids.split(',') if x.strip()]
            all_tipo_ids = set()
            for cid in tipo_ids:
                try:
                    tipo = Tipo.objects.get(id=cid)
                    all_tipo_ids.update(tipo.get_descendants(include_self=True).values_list('id', flat=True))
                except Tipo.DoesNotExist: pass
            filtros['rutina__tipo_id__in'] = list(all_tipo_ids)
        
        # 1. Fetch real Work Orders
        color_subquery = Horario.objects.filter(programaciones=OuterRef('programacion_id')).values('color')[:1]
        
        ordenes_qs = OrdenTrabajo.objects.filter(**filtros).select_related(
            'ubicacion', 'rutina__tipo', 'rutina__frecuencia'
        ).annotate(
            color_horario=Subquery(color_subquery)
        ).values(
            'id', 'rutina__nombre', 'ubicacion__nombre', 'ubicacion_id', 
            'rutina__tipo_id', 'inicio_programado', 'estado', 
            'color_horario', 'programacion_id', 'rutina__es_invasiva'
        )
        
        ordenes_list = list(ordenes_qs)
        existing_ot_keys = set((ot['programacion_id'], ot['inicio_programado'].date()) for ot in ordenes_list if ot.get('programacion_id'))
        
        # 2. Handle Projections (Ghost OTs)
        proy_filtros = {'fecha_inicio__year__lte': year}
        if programacion_id:
            proy_filtros['id'] = programacion_id

        if rutina_id:
            proy_filtros['rutina_id'] = rutina_id
        
        if tipo_ids:
            proy_filtros['rutina__tipo_id__in'] = list(all_tipo_ids)
            
        proyecciones = Programacion.objects.filter(**proy_filtros).select_related(
            'rutina__tipo', 'rutina__frecuencia'
        ).prefetch_related('horarios', 'areas')
        
        if ubicacion_ids:
            proyecciones = proyecciones.filter(areas__id__in=list(all_ids)).distinct()
            
        restricciones = set(RestriccionCalendario.objects.values_list('fecha', flat=True))
        working_days_cache = {}
        
        for prog in proyecciones:
            if not prog.rutina or not prog.rutina.frecuencia:
                continue
            fecha_ciclo = prog.fecha_inicio
            limite = min(prog.fecha_fin or (prog.fecha_inicio + timedelta(days=365)), date(year, 12, 31))
            frec_dias = prog.rutina.frecuencia.dias
            # Usar el primer horario encontrado o uno por defecto
            primer_horario = prog.horarios.first()
            color = primer_horario.color if primer_horario else '#94a3b8'
            
            # Combinar días de todos los horarios
            working_days = set()
            for h in prog.horarios.all():
                working_days.update(h.dias.values_list('dia', flat=True))
            if not working_days:
                working_days = set(range(7))

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
                        'rutina__tipo_id': prog.rutina.tipo_id,
                        'inicio_programado': datetime.combine(fecha_proyectada, datetime.min.time()),
                        'estado': 'PROYECCION',
                        'programacion__horario__color': color,
                        'programacion_id': prog.id,
                        'rutina__es_invasiva': prog.rutina.es_invasiva
                    })
                
                fecha_ciclo += timedelta(days=frec_dias)

        # 3. Grouping logic
        categorias = {c.id: c for c in Tipo.objects.all()}
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
                cat_id = ot['rutina__tipo_id']
                if cat_id and cat_id in categorias:
                    root = categorias[cat_id].get_root()
                    group_label = root.nombre
                    sub_label = categorias[cat_id].nombre if categorias[cat_id].id != root.id else "General"
                else:
                    group_label = "General / Otros"
                    sub_label = "Sin Tipo"
                    
            grupos_dict[group_label][sub_label][ot['rutina__nombre'] or "General"][semana_idx].append(ot)
            
        return {
            'grupos_dict': grupos_dict,
            'year': year,
            'semanas': WorkOrderService._generate_weeks_metadata(year)
        }

    @staticmethod
    def _generate_weeks_metadata(year):
        """Generates metadata for 52 weeks starting from Jan 1st."""
        weeks = []
        meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        
        for i in range(52):
            start = date(year, 1, 1) + timedelta(days=i*7)
            end = start + timedelta(days=6)
            if end.year > year: end = date(year, 12, 31)
            
            # Determinar el mes de la semana (usamos el inicio)
            mes_idx = start.month - 1
            
            weeks.append({
                'id': i,
                'label': f"Sem {i+1}",
                'start': start,
                'end': end,
                'mes': meses_nombres[mes_idx]
            })
        return weeks

    @staticmethod
    def get_grouped_tree(year):
        """Logic for grouping orders by Tipo > Subtipo > Frequency > Routine"""
        ordenes = OrdenTrabajo.objects.filter(inicio_programado__year=year).select_related(
            'rutina__tipo', 'rutina__frecuencia', 'ubicacion'
        ).prefetch_related('programacion__horarios__dias', 'activos').order_by(
            'rutina__tipo__nombre', 'rutina__nombre', 'inicio_programado'
        )
        
        categorias_full = {c.id: c for c in Tipo.objects.all()}
        for cat in categorias_full.values():
            if cat.padre_id:
                cat.padre = categorias_full.get(cat.padre_id)

        tree = {}
        for ot in ordenes:
            rut = ot.rutina
            cat = rut.tipo if rut else None
            
            if cat:
                if cat.id in categorias_full:
                    cat = categorias_full[cat.id]
                dis_name = cat.get_root().nombre
                sub_name = cat.nombre
            else:
                dis_name = "SIN TIPO"
                sub_name = "GENERAL"
                
            frec = rut.frecuencia if rut else None
            f_key = (frec.dias, frec.nombre) if frec and frec.dias is not None else (float('inf'), "SIN FRECUENCIA")
            r_key = rut.id if rut else 0

            if dis_name not in tree: tree[dis_name] = {}
            if sub_name not in tree[dis_name]: tree[dis_name][sub_name] = {}
            if f_key not in tree[dis_name][sub_name]: tree[dis_name][sub_name][f_key] = {}
            if r_key not in tree[dis_name][sub_name][f_key]:
                horario_obj = ot.programacion.horarios.first() if ot.programacion else None
                tree[dis_name][sub_name][f_key][r_key] = {
                    'nombre': rut.nombre if rut else "OT",
                    'descripcion': (rut.descripcion if rut else "") or "Sin descripción",
                    'horario_nombre': horario_obj.nombre if horario_obj else "N/A",
                    'horario_completo': (horario_obj.resumen_corto() if hasattr(horario_obj, 'resumen_corto') else horario_obj.nombre) if horario_obj else "N/A",
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
        """Logic for grouping orders by Tipo > Routine > Ubicacion"""
        ordenes = OrdenTrabajo.objects.filter(inicio_programado__year=year).select_related(
            'rutina__tipo', 'rutina__frecuencia', 'ubicacion'
        ).order_by('rutina__tipo__nombre', 'rutina__nombre', 'ubicacion__nombre', 'inicio_programado')
        
        categorias_full = {c.id: c for c in Tipo.objects.all()}
        for cat in categorias_full.values():
            if cat.padre_id: cat.padre = categorias_full.get(cat.padre_id)

        tree = {}
        for ot in ordenes:
            rut = ot.rutina
            if not rut: continue
            cat = rut.tipo
            if cat:
                cat = categorias_full.get(cat.id) or cat
                dis_name = cat.get_root().nombre
                sub_name = cat.nombre
            else:
                dis_name = "SIN TIPO"; sub_name = "GENERAL"
            
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
    @staticmethod
    def get_location_grouped_tree(year, month, ubicacion_ids=None, tipo_ids=None):
        """
        Agrupa órdenes por:
        1. Ubicación Raíz (Edificio) -> Mapeado a 'sys' en template
        2. Sub-ubicación (Piso/Área) -> Mapeado a 'sub' en template (key: subs)
        3. Categoría (Sistema)       -> Mapeado a 'rut' en template (key: rutinas)
        4. Rutina                    -> Mapeado a 'ubi' en template (key: ubicaciones)
        5. Activo                    -> Mapeado a 'asset' en template (key: activos)
        """
        from activos.models import Ubicacion
        _, num_days = calendar.monthrange(year, month)
        days_range = range(1, num_days + 1)
        
        filtros = {
            'inicio_programado__year': year,
            'inicio_programado__month': month
        }
        
        if ubicacion_ids:
            all_ids = set()
            for uid in ubicacion_ids:
                try:
                    area = Ubicacion.objects.get(id=uid)
                    all_ids.update(area.get_descendants(include_self=True).values_list('id', flat=True))
                except Ubicacion.DoesNotExist: pass
            filtros['ubicacion_id__in'] = list(all_ids)
            
        if tipo_ids:
            all_tipo_ids = set()
            for cid in tipo_ids:
                try:
                    tipo = Tipo.objects.get(id=cid)
                    all_tipo_ids.update(tipo.get_descendants(include_self=True).values_list('id', flat=True))
                except Tipo.DoesNotExist: pass
            filtros['rutina__tipo_id__in'] = list(all_tipo_ids)

        ordenes = OrdenTrabajo.objects.filter(**filtros).select_related(
            'rutina__tipo', 'rutina__frecuencia', 'ubicacion'
        ).prefetch_related('programacion__horarios__dias', 'activos__modelo__categoria')
        
        # Pre-fetch locations and cache hierarchy
        all_locs = {l.id: l for l in OrdenTrabajo.ubicacion.field.related_model.objects.all()}
        
        def get_root_and_sub(loc_id):
            if not loc_id or loc_id not in all_locs:
                return ("Sin Ubicación", "General")
            
            curr = all_locs[loc_id]
            # Si no tiene padre, es raiz
            if not curr.padre_id:
                return (curr.nombre, "General")
                
            # Buscar raiz subiendo
            path = [curr]
            p = curr
            while p.padre_id and p.padre_id in all_locs:
                p = all_locs[p.padre_id]
                path.append(p)
            
            root = path[-1]
            # El sub es el hijo directo del root en el path, o el mismo root si es corto
            # path está ordenado [hoja, ..., raiz]
            # si len > 1, path[-2] es hijo de raiz
            sub = path[-2] if len(path) > 1 else root 
            
            # Ajuste especifico: Si queremos que Sub-ubicacion sea la ubicación directa de la OT:
            # return (root.nombre, curr.nombre)
            
            # Ajuste para jerarquía estricta (Edificio -> Piso):
            return (root.nombre, sub.nombre)

        # Structure: Tree[Root][Sub][Category][Routine][AssetCat][AssetKey][Day] -> List of OTs
        tree = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))))))
        
        system_colors = {} # To store colors based on root
        
        for ot in ordenes:
            root_name, sub_name = get_root_and_sub(ot.ubicacion_id)
            
            cat_name = ot.rutina.tipo.nombre if ot.rutina and ot.rutina.tipo else "Sin Tipo"
            rut_name = ot.rutina.nombre if ot.rutina else "OT Sin Rutina"
            
            # Color logic (optional, reuse existing or random)
            primer_horario = ot.programacion.horarios.first() if ot.programacion else None
            color = primer_horario.color if primer_horario else '#94a3b8'
            if root_name not in system_colors:
                system_colors[root_name] = color

            sd = timezone.localtime(ot.inicio_programado)
            ed = timezone.localtime(ot.fin_programado or ot.inicio_programado)
            nc = max(1, math.ceil((ed - sd).total_seconds() / 86400))
            
            assets = list(ot.activos.all())
            
            for i in range(nc):
                cd = sd.date() + timedelta(days=i)
                if cd.year == year and cd.month == month:
                    dp = 'single' if nc == 1 else ('start' if i == 0 else ('end' if i == nc - 1 else 'middle'))
                    
                    base_info = {
                        'id': ot.id, 
                        'estado': ot.estado, 
                        'inicio_iso': sd.strftime('%Y-%m-%d'), 
                        'inicio_hm': sd.strftime('%H:%M'), 
                        'fin_full': ed.strftime('%d/%m/%Y %H:%M'), 
                        'fin_hm': ed.strftime('%H:%M'), 
                        'rutina_nombre': rut_name, 
                        'activos_nombres': ", ".join([a.nombre for a in assets]), 
                        'duration_pos': dp, 
                        'color': '#ef4444' if (ot.rutina and ot.rutina.es_invasiva) else color
                    }

                    if not assets:
                        asset_key = (0, "General") 
                        # Consistent 7-level structure
                        tree[root_name][sub_name][cat_name][rut_name]["General"][asset_key][cd.day].append(base_info)
                    else:
                        for idx, a in enumerate(assets):
                            info = base_info.copy()
                            if len(assets) > 1:
                                info['group_type'] = 'start' if idx == 0 else ('end' if idx == len(assets) - 1 else 'middle')
                            
                            asset_key = (a.id, a.nombre)
                            asset_cat = a.modelo.categoria.nombre if (a.modelo and a.modelo.categoria) else "General"
                            tree[root_name][sub_name][cat_name][rut_name][asset_cat][asset_key][cd.day].append(info)

        # Convert to list structure for template
        ft = []
        for sys in sorted(tree.keys()): # Root Location
            subs = []; sda = collections.defaultdict(bool)
            for sub in sorted(tree[sys].keys()): # Sub Location
                rcats = []; subda = collections.defaultdict(bool)
                for rcat in sorted(tree[sys][sub].keys()): # Routine Category (Discipline)
                    ruts = []; rcda = collections.defaultdict(bool)
                    for rut in sorted(tree[sys][sub][rcat].keys()): # Routine
                        acats = []; rda = collections.defaultdict(bool)
                        for acat in sorted(tree[sys][sub][rcat][rut].keys()): # Asset Category
                            assets_l = []; ada = collections.defaultdict(bool)
                            for ak in sorted(tree[sys][sub][rcat][rut][acat].keys(), key=lambda x: x[1]): # Asset
                                cells = []
                                for d in days_range:
                                    ots = tree[sys][sub][rcat][rut][acat][ak].get(d, [])
                                    active = len(ots) > 0
                                    gt = ots[0].get('group_type') if ots else None
                                    cells.append({'day': d, 'ots': ots, 'active': active, 'group_type': gt})
                                    if active: sda[d]=True; subda[d]=True; rcda[d]=True; rda[d]=True; ada[d]=True
                                assets_l.append({'label': ak[1], 'id': ak[0], 'celdas': cells})
                            acats.append({'label': acat, 'celdas': [{'day': d, 'active': ada[d]} for d in days_range], 'activos': assets_l})
                        ruts.append({'label': rut, 'celdas': [{'day': d, 'active': rda[d]} for d in days_range], 'categorias': acats})
                    rcats.append({'label': rcat, 'celdas': [{'day': d, 'active': rcda[d]} for d in days_range], 'rutinas': ruts})
                subs.append({'label': sub, 'celdas': [{'day': d, 'active': subda[d]} for d in days_range], 'rutinas': rcats})
            ft.append({'label': sys, 'color': system_colors.get(sys, "#64748b"), 'celdas': [{'day': d, 'active': sda[d]} for d in days_range], 'subs': subs})
        return ft
            

    @staticmethod
    def save_ot_pdf_as_attachment(ot_id):
        """
        Generates the PDF for an OT and saves it as an attachment.
        Used by background tasks.
        """
        ot = OrdenTrabajo.objects.get(pk=ot_id)
        
        # Check if it already exists to avoid duplicates (with the same name)
        filename = f"OT_{ot.id}.pdf"
        existing = ArchivoOrdenTrabajo.objects.filter(orden_trabajo=ot, nombre=filename).first()
        
        # Calcular URL del PDF (existente o futura)
        pdf_url = None
        if existing and existing.archivo:
            pdf_url = f"{settings.SITE_URL}{existing.archivo.url}"
        else:
            pdf_url = f"{settings.SITE_URL}/media/mantenimiento/ot/{filename}"

        pdf_bytes = generate_ot_pdf_bytes(ot, pdf_url=pdf_url)
        
        if existing:
            existing.archivo.save(filename, ContentFile(pdf_bytes), save=True)
            return existing
        else:
            nuevo_archivo = ArchivoOrdenTrabajo(
                orden_trabajo=ot,
                nombre=filename,
                tipo='DOCUMENTO'
            )
            nuevo_archivo.archivo.save(filename, ContentFile(pdf_bytes), save=True)
            return nuevo_archivo
