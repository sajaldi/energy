from django.urls import path
from . import views
from .views import mobile_crear_solicitud
from .api_materials import api_list_materials, api_list_categories, api_master_sync, api_precios_historicos, api_create_material, api_material_detail, api_material_update, api_search_codigos_exoneracion, api_export_materials_excel

app_name = 'inventarios'

urlpatterns = [
    path('', views.inventario_dashboard, name='dashboard'),
    path('solicitud/<int:pk>/detalle/', views.solicitud_detalle_rapido, name='solicitud_detalle_rapido'),
    path('solicitud/<int:pk>/update/', views.solicitud_update_rapido, name='solicitud_update_rapido'),
    path('crear-solicitud/', views.crear_solicitud_dashboard, name='crear_solicitud'),
    path('api/stock/<int:material_id>/', views.api_get_material_stock, name='api_get_material_stock'),
    path('api/material/<int:material_id>/update/', views.api_update_material_mobile, name='api_update_material_mobile'),
    path('cart/add/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:material_id>/', views.cart_remove, name='cart_remove'),
    path('cart/detail/', views.cart_detail_view, name='cart_detail'),
    path('cart/checkout/', views.cart_checkout, name='cart_checkout'),
    path('escanear/', views.scanner_view, name='scanner'),
    path('api/sku/', views.api_get_material_by_sku, name='api_get_material_by_sku'),
    path('api/movimiento-rapido/', views.api_registrar_movimiento_rapido, name='api_registrar_movimiento_rapido'),
    
    # API para selector visual
    path('api/materials/', api_list_materials, name='api_list_materials'),
    path('api/materials/create/', api_create_material, name='api_create_material'),
    path('api/material/<int:material_id>/detail/', api_material_detail, name='api_material_detail'),
    path('api/material/<int:material_id>/update/', api_material_update, name='api_material_update'),
    path('api/codigos-exoneracion/search/', api_search_codigos_exoneracion, name='api_search_codigos_exoneracion'),
    path('api/categories/', api_list_categories, name='api_list_categories'),
    path('api/materials/export/', api_export_materials_excel, name='api_export_materials_excel'),
    path('catalogo/', views.master_catalog, name='master_catalog'),
    path('nuevos-materiales/', views.solicitud_nuevos_materiales, name='solicitud_nuevos_materiales'),
    path('admin-catalogos/', views.admin_catalogos, name='admin_catalogos'),
    path('categorias/', views.categorias_visualizer, name='categorias_visualizer'),

    # Mobile Views
    path('mobile/dashboard/', views.mobile_inventario_dashboard, name='mobile_dashboard'),
    path('mobile/movimientos/', views.mobile_historial_movimientos, name='mobile_movimientos'),
    path('mobile/pedidos/', views.mobile_lista_pedidos, name='mobile_lista_pedidos'),
    path('mobile/pedidos/<int:pk>/', views.mobile_detalle_pedido, name='mobile_detalle_pedido'),
    path('mobile/crear-solicitud/', mobile_crear_solicitud, name='mobile_crear_solicitud'),
    path('api/crear-ot-rapida/', views.api_crear_ot_rapida, name='api_crear_ot_rapida'),
    path('mobile/catalog/', views.mobile_catalog, name='mobile_catalog'),
    path('mobile/gestion-salidas/', views.mobile_gestion_salidas_view, name='mobile_gestion_salidas'),
    path('mobile/devolucion/', views.mobile_devolucion_view, name='mobile_devolucion'),
    path('mobile/devolucion/historial/', views.mobile_historial_devoluciones_view, name='mobile_historial_devoluciones'),
    path('mobile/modificacion-inventario/', views.mobile_modificacion_inventario, name='mobile_modificacion_inventario'),
    path('api/devolucion/registrar/', views.api_registrar_devolucion, name='api_registrar_devolucion'),
    path('api/conteo-inventario/guardar/', views.api_guardar_conteo_inventario, name='api_guardar_conteo_inventario'),
    path('api/usuarios/search/', views.api_search_usuarios, name='api_search_usuarios'),
    path('api/ordenes-trabajo/search/', views.api_search_ordenes_trabajo, name='api_search_ot'),
    path('api/niveles/', views.api_niveles_por_edificio, name='api_niveles_edificio'),

    # Impresión de Etiquetas
    path('etiquetas/', views.imprimir_etiquetas_view, name='imprimir_etiquetas'),
    path('etiquetas/generar-pdf/', views.generar_pdf_etiquetas, name='generar_pdf_etiquetas'),
    path('api/print-label/<int:material_id>/', views.api_print_label, name='api_print_label'),
    path('api/ingreso-lote/', views.api_ingreso_lote, name='api_ingreso_lote'),
    path('api/solicitudes/search/', views.api_list_solicitudes, name='api_list_solicitudes'),
    path('api/solicitudes/<int:pk>/autorizar/', views.api_autorizar_solicitud, name='api_autorizar_solicitud'),
    path('aprobar/<int:pk>/<str:token>/', views.formulario_aprobacion_solicitud, name='formulario_aprobacion'),
    path('api/sync-offline-queue/', views.api_sync_offline_queue, name='api_sync_offline_queue'),
    path('api/solicitudes/<str:pk>/items/', views.api_get_solicitud_items, name='api_get_solicitud_items'),
    path('api/material/quick-create/', views.api_create_material, name='api_create_material'),
    path('api/pedidos-pendientes/', views.api_pedidos_pendientes_almacen, name='api_pedidos_pendientes_almacen'),
    path('api/pedidos/<int:pk>/detalle/', views.api_detalle_solicitud_almacen, name='api_detalle_solicitud_almacen'),
    path('api/pedidos/<int:pk>/despachar/', views.api_despachar_solicitud, name='api_despachar_solicitud'),
    path('api/discrepancy/resolve/', views.api_resolver_discrepancia, name='api_resolver_discrepancia'),
    path('api/movimiento/<int:mov_id>/liquidar/', views.api_liquidar_movimiento, name='api_liquidar_movimiento'),
    path('api/movimiento/<int:mov_id>/detalle/', views.api_detalle_movimiento, name='api_detalle_movimiento'),
    path('api/movimiento/<int:mov_id>/vincular-ot/', views.api_vincular_ot_movimiento, name='api_vincular_ot_movimiento'),
    path('api/sync-master/', api_master_sync, name='api_master_sync'),
    path('api/check-ot-solicitud/<int:ot_id>/', views.api_check_ot_solicitud, name='api_check_ot_solicitud'),
    path('api/material/<int:material_id>/precios-historicos/', api_precios_historicos, name='api_precios_historicos'),
    path('api/solicitudes/<int:pk>/update-items/', views.api_solicitud_update_items, name='api_solicitud_update_items'),
    path('api/solicitudes/<int:pk>/resend-webhook/', views.api_resolicitud_webhook, name='api_resolicitud_webhook'),
    path('api/recalcular-stock/<int:material_id>/', views.api_recalcular_stock, name='api_recalcular_stock'),
    path('registrar-salida/', views.registrar_salida_view, name='registrar_salida'),
    path('manifest.json', views.pwa_manifest, name='pwa_manifest'),
    path('sw.js', views.pwa_sw, name='pwa_sw'),

    # Racks
    path('racks/', views.rack_list_view, name='racks_list'),
    path('racks/<int:pk>/3d/', views.rack_3d_view, name='rack_3d'),
    path('api/racks/<int:rack_id>/position/assign/', views.api_rack_assign_position, name='api_rack_assign'),
    path('api/racks/<int:rack_id>/position/remove/', views.api_rack_remove_position, name='api_rack_remove'),
    path('api/racks/<int:rack_id>/position/', views.api_rack_update_position, name='api_rack_position'),
    path('api/bodega/<int:bodega_id>/racks/', views.api_bodega_racks, name='api_bodega_racks'),
    path('bodega/<int:pk>/3d/', views.bodega_3d_view, name='bodega_3d'),
    # Calendario de Almacén
    path('calendario/', views.calendario_view, name='calendario'),
    path('api/calendario/eventos/', views.api_calendario_eventos, name='api_calendario_eventos'),
    path('api/calendario/slots/', views.api_calendario_slots, name='api_calendario_slots'),
    path('api/calendario/slots/<int:slot_id>/', views.api_calendario_slots, name='api_calendario_slots_detail'),
    path('api/calendario/horarios/', views.api_calendario_horarios, name='api_calendario_horarios'),
    path('api/calendario/requisicion/<uuid:pk>/items/', views.api_calendario_requisicion_items, name='api_calendario_requisicion_items'),
    path('api/calendario/disponibilidad/<str:fecha>/', views.api_calendario_disponibilidad_diaria, name='api_calendario_disponibilidad'),

    # API: Materiales Utilizados por OT (vinculación OT ↔ Activo ↔ Material)
    path('api/ot/<int:ot_id>/materiales-utilizados/', views.api_materiales_utilizados_ot, name='api_materiales_utilizados_ot'),
    path('api/material-utilizado/<int:registro_id>/delete/', views.api_materiales_utilizados_ot_delete, name='api_materiales_utilizados_ot_delete'),
    path('api/activo/<int:activo_id>/historial-materiales/', views.api_historial_materiales_activo, name='api_historial_materiales_activo'),
    path('api/material/<int:material_id>/vincular-activo/', views.api_vincular_material_activo, name='api_vincular_material_activo'),
    path('api/activos/search/', views.api_search_activos, name='api_search_activos'),
    path('api/marcas/search/', views.api_search_marcas, name='api_search_marcas'),

    # Ajuste Masivo (solo Auditoria)
    path('ajuste-masivo/', views.ajuste_masivo_view, name='ajuste_masivo'),
    path('api/ajuste-masivo/procesar/', views.api_ajuste_masivo_procesar, name='api_ajuste_masivo_procesar'),
    path('api/ajuste-masivo/catalogo/', views.api_ajuste_masivo_catalogo, name='api_ajuste_masivo_catalogo'),
]