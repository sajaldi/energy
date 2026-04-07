import pandas as pd
from django.db import transaction
from .models import SolicitudTicket
from activos.models.ubicacion import Ubicacion
from django.utils import timezone
import math

@transaction.atomic
def import_tickets_from_df(df):
    """
    Importa tickets desde un DataFrame de pandas de manera OPTIMIZADA (Bulk).
    """
    if df.empty:
        return 0, 0

    # 1. Obtener todos los IDs de solicitud del Excel
    df['id_sol_int'] = pd.to_numeric(df['ID Solicitud servicio'], errors='coerce')
    df = df.dropna(subset=['id_sol_int'])
    all_ids = df['id_sol_int'].unique().astype(int).tolist()

    # 2. Consultar registros existentes por ID o por Folio (para unificar los de webhook)
    from django.db.models import Q
    folios_in_excel = df['foliosolicitudservicio'].dropna().unique().tolist()
    
    existing_tickets = SolicitudTicket.objects.filter(
        Q(id_solicitud__in=all_ids) | Q(folio__in=folios_in_excel)
    )
    
    existing_by_id = {t.id_solicitud: t for t in existing_tickets}
    existing_by_folio = {t.folio: t for t in existing_tickets if t.folio}

    # 3. Pre-cargar Ubicaciones para mapeo inteligente
    # Tickets 'Nivel' -> Ubicacion 'EDIFICIO'
    # Tickets 'Grupo' -> Ubicacion 'NIVEL' (hijo de Edificio)
    all_ubicaciones = Ubicacion.objects.all().select_related('padre')
    
    # Mapa de Edificios: {nombre: obj}
    edificios_map = {u.nombre.upper(): u for u in all_ubicaciones if u.tipo == 'EDIFICIO'}
    
    # Mapa de Niveles: {(nombre, padre_id): obj}
    niveles_map = {(u.nombre.upper(), u.padre_id): u for u in all_ubicaciones if u.tipo == 'NIVEL'}

    to_create = []
    to_update = []
    creados = 0
    actualizados = 0

    # Funciones auxiliares de limpieza
    def clean(val):
        if pd.isna(val): return None
        return str(val).strip()

    def parse_date(val):
        if pd.isna(val) or val == 'None' or val == '': return None
        try:
            dt = pd.to_datetime(val)
            if pd.isna(dt): return None
            if timezone.is_naive(dt):
                return timezone.make_aware(dt)
            return dt
        except:
            return None

    # Columnas que vamos a actualizar en bulk_update
    update_fields = [
        'folio', 'solicitante', 'responsable', 'solicitud_descripcion',
        'falla_descripcion', 'falla_clasificacion', 'servicio', 'subservicio',
        'unidad', 'area', 'grupo', 'nivel', 'fecha_solicitud', 'tipo_recepcion',
        'fecha_tipo_recepcion', 'fecha_suspension', 'fecha_cierre', 'tipo_solicitud',
        'tiempo_tipo', 'fecha_diagnostico', 'diagnostico', 'fecha_actividades',
        'actividades', 'fecha_observaciones', 'observaciones',
        'fecha_observaciones_usuario', 'observaciones_usuario',
        'clasificacion_falla_final', 'categoria_falla', 'ubicacion',
        'correo_cierre', 'cierre_enviado'
    ]

    for _, row in df.iterrows():
        id_sol_int = int(row['id_sol_int'])
        
        data = {
            'folio': clean(row.get('foliosolicitudservicio')),
            'solicitante': clean(row.get('solicitud_solicitante')),
            'responsable': clean(row.get('Responsable_atencion')),
            'solicitud_descripcion': clean(row.get('solicitud_descripcion')),
            'falla_descripcion': clean(row.get('falla_descripcion')),
            'falla_clasificacion': clean(row.get('falla_clasificacion')),
            'servicio': clean(row.get('servicio')),
            'subservicio': clean(row.get('subservicio')),
            'unidad': clean(row.get('unidad')),
            'area': clean(row.get('area')),
            'grupo': clean(row.get('grupo')),
            'nivel': clean(row.get('nivel')),
            'fecha_solicitud': parse_date(row.get('solicitud_fecha')),
            'tipo_recepcion': clean(row.get('TipoRecepcion')),
            'fecha_tipo_recepcion': parse_date(row.get('Fecha_TipoRecepcion')),
            'fecha_suspension': parse_date(row.get('suspencion_fecha')),
            'fecha_cierre': parse_date(row.get('cerro_fecha')),
            'tipo_solicitud': clean(row.get('solicitud_tipo')),
            'tiempo_tipo': clean(row.get('tiempo_tipo')),
            'fecha_diagnostico': parse_date(row.get('FechaHora_Diagnostico')),
            'diagnostico': clean(row.get('Diagnostico')),
            'fecha_actividades': parse_date(row.get('FechaHora_Actividades')),
            'actividades': clean(row.get('Actividades')),
            'fecha_observaciones': parse_date(row.get('FechaHora_Observaciones')),
            'observaciones': clean(row.get('Observaciones')),
            'fecha_observaciones_usuario': parse_date(row.get('FechaHora_ObservacionesUsuario')),
            'observaciones_usuario': clean(row.get('ObservacionesUsuario')),
            'clasificacion_falla_final': clean(row.get('Clasificacion_Falla')),
            'categoria_falla': clean(row.get('Categoria_Falla')),
            'correo_cierre': False,
            'cierre_enviado': False,
        }

        # --- Resolución de Ubicación Normalizada ---
        data['ubicacion'] = resolve_ticket_ubicacion(data['nivel'], data['grupo'])

        # Lógica de emparejamiento inteligente
        obj = existing_by_id.get(id_sol_int)
        if not obj and data['folio']:
            obj = existing_by_folio.get(data['folio'])
            if obj:
                # Si lo encontramos por Folio pero no por ID, actualizamos el ID 
                # al oficial que viene del Excel de GIA
                obj.id_solicitud = id_sol_int

        if obj:
            # Actualizar objeto existente en memoria
            for field, val in data.items():
                setattr(obj, field, val)
            to_update.append(obj)
            actualizados += 1
            # Actualizar los mapas para evitar duplicados en el mismo loop
            existing_by_id[id_sol_int] = obj
            if data['folio']:
                existing_by_folio[data['folio']] = obj
        else:
            # Crear instancia nueva
            new_ticket = SolicitudTicket(id_solicitud=id_sol_int, **data)
            to_create.append(new_ticket)
            creados += 1
            # Registrar en mapas para filas duplicadas en el excel
            existing_by_id[id_sol_int] = new_ticket
            if data['folio']:
                existing_by_folio[data['folio']] = new_ticket

    # 3. Ejecutar operaciones en lotes
    if to_create:
        # ignore_conflicts=True evita que un duplicate key aborte toda la transacción.
        # Los tickets ya existentes (por race condition o webhook previo) son ignorados aquí
        # y se tratan con update_or_create a continuación para garantizar que sus datos
        # estén actualizados.
        created_objs = SolicitudTicket.objects.bulk_create(
            to_create, batch_size=100, ignore_conflicts=True
        )
        # Detectar cuáles NO se insertaron (ya existían) y actualizarlos individualmente
        created_ids = {obj.id_solicitud for obj in created_objs if obj.pk}
        conflicts = [obj for obj in to_create if obj.id_solicitud not in created_ids]
        for obj in conflicts:
            data_fields = {f: getattr(obj, f) for f in update_fields}
            SolicitudTicket.objects.filter(id_solicitud=obj.id_solicitud).update(**data_fields)
            actualizados += 1
            creados -= 1  # No era un nuevo registro, ajustar contador
 
    if to_update:
        SolicitudTicket.objects.bulk_update(to_update, update_fields, batch_size=100)

    return creados, actualizados

def resolve_ticket_ubicacion(nombre_edificio, nombre_nivel):
    """
    Resuelve o crea objetos de Ubicacion basados en la jerarquía de Tickets.
    nombre_edificio: En Tickets suele venir en el campo 'nivel'
    nombre_nivel: En Tickets suele venir en el campo 'grupo'
    """
    if not nombre_edificio:
        return None
        
    # Buscar o crear Edificio
    edif_obj, _ = Ubicacion.objects.get_or_create(
        nombre=nombre_edificio.strip(), 
        tipo='EDIFICIO'
    )
    
    if not nombre_nivel:
        return edif_obj
        
    # Buscar o crear Nivel/Piso bajo el edificio
    nivel_obj, _ = Ubicacion.objects.get_or_create(
        nombre=nombre_nivel.strip(),
        tipo='NIVEL',
        padre=edif_obj
    )
    
    return nivel_obj

def calcular_horas_habiles(desde, hasta):
    """
    Calcula las horas hábiles entre dos fechas (desde y hasta).
    Regla:
    - Ventana: 07:00 a 23:00 (16 horas).
    - Excluir Sábados (5) y Domingos (6).
    - Excluir Feriados de mantenimiento.RestriccionCalendario.
    """
    from mantenimiento.models import RestriccionCalendario
    from datetime import time, timedelta, datetime
    from django.utils import timezone
    
    if not desde or not hasta or hasta <= desde:
        return 0.0

    # Asegurar que ambos sean aware
    if timezone.is_naive(desde):
        desde = timezone.make_aware(desde)
    if timezone.is_naive(hasta):
        hasta = timezone.make_aware(hasta)

    # Obtener feriados en el rango
    feriados = set(RestriccionCalendario.objects.filter(
        fecha__range=(desde.date(), hasta.date())
    ).values_list('fecha', flat=True))

    total_segundos = 0
    
    # Definir ventana laboral
    h_inicio = time(7, 0)
    h_fin = time(23, 0)

    # Iterar por cada día en el rango
    current_date = desde.date()
    while current_date <= hasta.date():
        # Excluir fines de semana (Sábado=5, Domingo=6) y feriados
        if current_date.weekday() < 5 and current_date not in feriados:
            # Inicio y fin de la jornada para este día
            jornada_inicio = timezone.make_aware(datetime.combine(current_date, h_inicio))
            jornada_fin = timezone.make_aware(datetime.combine(current_date, h_fin))
            
            # El tiempo efectivo es el solapamiento entre [desde, hasta] y [jornada_inicio, jornada_fin]
            overlap_inicio = max(desde, jornada_inicio)
            overlap_fin = min(hasta, jornada_fin)
            
            if overlap_inicio < overlap_fin:
                total_segundos += (overlap_fin - overlap_inicio).total_seconds()
        
        current_date += timedelta(days=1)
            
    return round(total_segundos / 3600.0, 2)
