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

    # 2. Consultar registros existentes para decidir qué es nuevo y qué es actualización
    existing_tickets = SolicitudTicket.objects.filter(id_solicitud__in=all_ids)
    existing_map = {t.id_solicitud: t for t in existing_tickets}

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
        'clasificacion_falla_final', 'categoria_falla', 'ubicacion'
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
        }

        # --- Resolución de Ubicación Normalizada ---
        nombre_edificio = data['nivel'] # En Tickets es Edificio
        nombre_nivel = data['grupo']   # En Tickets es Nivel (Grupo)
        resolved_ubicacion = None

        if nombre_edificio:
            key_edif = nombre_edificio.upper()
            edif_obj = edificios_map.get(key_edif)
            if not edif_obj:
                # Crear edificio si no existe
                edif_obj = Ubicacion.objects.create(nombre=nombre_edificio, tipo='EDIFICIO')
                edificios_map[key_edif] = edif_obj
            
            resolved_ubicacion = edif_obj # Default al edificio if no nivel

            if nombre_nivel:
                key_nivel = (nombre_nivel.upper(), edif_obj.id)
                nivel_obj = niveles_map.get(key_nivel)
                if not nivel_obj:
                    # Crear nivel bajo el edificio
                    nivel_obj = Ubicacion.objects.create(nombre=nombre_nivel, tipo='NIVEL', padre=edif_obj)
                    niveles_map[key_nivel] = nivel_obj
                
                resolved_ubicacion = nivel_obj

        data['ubicacion'] = resolved_ubicacion

        if id_sol_int in existing_map:
            # Actualizar objeto existente en memoria
            obj = existing_map[id_sol_int]
            for field, val in data.items():
                setattr(obj, field, val)
            to_update.append(obj)
            actualizados += 1
        else:
            # Crear instancia nueva
            to_create.append(SolicitudTicket(id_solicitud=id_sol_int, **data))
            creados += 1

    # 3. Ejecutar operaciones en lotes
    if to_create:
        SolicitudTicket.objects.bulk_create(to_create, batch_size=500)
    
    if to_update:
        SolicitudTicket.objects.bulk_update(to_update, update_fields, batch_size=500)

    return creados, actualizados
