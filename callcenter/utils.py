import pandas as pd
from .models import SolicitudTicket
from django.utils import timezone
import math

def import_tickets_from_df(df):
    """
    Importa tickets desde un DataFrame de pandas.
    Retorna (creados, actualizados)
    """
    total = len(df)
    creados = 0
    actualizados = 0

    for index, row in df.iterrows():
        id_solicitud = row.get('ID Solicitud servicio')
        if pd.isna(id_solicitud):
            continue
        
        # Limpiar datos y manejar NaNs
        def clean(val):
            if pd.isna(val): return None
            return str(val).strip()

        def parse_date(val):
            if pd.isna(val) or val == 'None' or val == '': return None
            try:
                dt = pd.to_datetime(val)
                if pd.isna(dt): return None
                return dt
            except:
                return None

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

        # Intentar forzar la conversión de ID Solicitud a int
        try:
            id_sol_int = int(id_solicitud)
        except:
            continue

        obj, created = SolicitudTicket.objects.update_or_create(
            id_solicitud=id_sol_int,
            defaults=data
        )
        
        if created:
            creados += 1
        else:
            actualizados += 1
            
    return creados, actualizados
