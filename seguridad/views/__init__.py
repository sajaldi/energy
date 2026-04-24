from .web import generar_permiso_de_ot, detalle_permiso_view
from .mobile import (
    mobile_mis_permisos, mobile_permiso_detalle, mobile_generar_permiso,
    mobile_confiscaciones_lista, mobile_confiscacion_nueva, mobile_confiscacion_ejecutar,
    mobile_confiscacion_agregar_objeto, mobile_confiscacion_objeto_actualizar,
    mobile_confiscacion_editar_objeto, mobile_confiscacion_confirmar_carga,
    api_confirmar_carga_objeto, mobile_almacen_recepcion, 
    mobile_almacen_validar_lote, api_almacen_almacenar_objeto,
    mobile_almacen_entrega_validar, api_almacen_confirmar_entrega,
    mobile_confiscacion_entrega_pdf_view,
    mobile_confiscacion_imprimir_etiqueta,
    mobile_perfil
)
from .pdf_views import (
    generar_permiso_pdf_view, mobile_confiscacion_pdf_view
)

