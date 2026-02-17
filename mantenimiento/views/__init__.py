from .cronograma import (
    calendario_mantenimiento, 
    calendario_detallado, 
    cronograma_mantenimiento_visual, 
    detalle_mes, 
    visualizador_proyecciones,
    wizard_cronograma,
    wizard_mensual,
    cronograma_mensual_matriz
)
from .api import (
    api_update_ot_date,
    api_split_ot_asset,
    api_merge_ots,
    api_bulk_update_ot_dates,
    api_delete_ots,
    api_get_notifications,
    api_mark_notification_read,
    api_get_assets_wizard,
    generar_ordenes_programacion,
    api_generar_orden_individual,
    api_search_ordenes
)
from .wizard import programar_rutina_wizard
from .mobile import (
    mobile_cronograma,
    mobile_programacion_detalle,
    mobile_ot_detalle,
    mobile_crear_aviso,
    mobile_ot_iniciar,
    mobile_ot_finalizar,
    mobile_crear_ot_rutina,
    mobile_mis_avisos,
    mobile_aviso_detalle
)
from .dashboard import dashboard_cargas
from . import import_personal
from . import import_procedimientos
