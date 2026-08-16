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
    api_search_ordenes,
    api_get_ot_detail,
    api_get_ot_related,
    api_update_ot_status_notes,
    api_buscar_activos,
    api_buscar_activos_filtrados,
    api_update_foto_descripcion,
    api_busqueda_global,
    api_ordenes_hoy,
    api_cerrar_ot,
    api_guardar_cierre
)
from .wizard import programar_rutina_wizard
from .mobile import (
    mobile_cronograma,
    mobile_programacion_detalle,
    mobile_ot_detalle,
    mobile_ot_update_ajax,
    mobile_ot_vincular_activo,
    mobile_crear_aviso,
    mobile_aviso_editar,
    mobile_ot_iniciar,
    mobile_ot_finalizar,
    mobile_crear_ot_rutina,
    mobile_mis_avisos,
    mobile_mis_ordenes,
    mobile_aviso_detalle, aviso_fiori_view,
    mobile_ot_upload_file,
    mobile_ot_delete_file,
    mobile_crear_medicion,
    check_ot_pdf_status,
    mobile_crear_otnp,
    mobile_ot_eliminar,
    mobile_ot_webhook,
    mobile_ot_update_file_name,
    mobile_crear_ot_desde_puesto,
    mobile_ot_whatsapp_webhook
)
from .dashboard import dashboard_cargas, asignar_puesto_ajax
from .dashboard_general import mantenimiento_dashboard, ordenes_lista_view, ordenes_bulk_delete, ordenes_bulk_status
from .ai_search import buscador_ia_cronograma, api_busqueda_ia
from . import import_personal
from . import import_procedimientos
from . import import_categorias
from . import pdf_views
from . import avisos_dashboard

