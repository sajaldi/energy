from django.urls import path
from . import views, views_import, views_autorizar, views_webhook, views_pagos, views_dashboard_api

app_name = 'presupuestos'

urlpatterns = [
    path('cronograma/<int:pk>/', views.cronograma_presupuesto, name='cronograma_detalle'),
    path('cronograma/grupo/<int:pk>/', views.cronograma_grupal, name='cronograma_grupal'),
    path('api/update_monto/', views.api_update_monto_mensual, name='api_update_monto'),
    path('api/update_item/', views.api_update_item, name='api_update_item'),
    path('api/create_item/', views.api_create_item, name='api_create_item'),
    path('api/create_partida/', views.api_create_partida, name='api_create_partida'),
    path('api/delete_item/', views.api_delete_item, name='api_delete_item'),
    path('api/delete_partida/', views.api_delete_partida, name='api_delete_partida'),
    path('api/update_partida/', views.api_update_partida, name='api_update_partida'),
    path('api/get_disciplinas/', views.api_get_disciplinas, name='api_get_disciplinas'),
    path('api/cronograma_celda/', views.api_cronograma_detalle_celda, name='api_cronograma_celda'),
    path('exportar_excel/<int:pk>/', views.exportar_cronograma_excel, name='exportar_excel'),
    path('exportar_pdf/<int:pk>/', views.exportar_cronograma_pdf, name='exportar_pdf'),
    path('exportar_grupo_pdf/<int:pk>/', views.exportar_cronograma_grupal_pdf, name='exportar_cronograma_grupal_pdf'),
    path('exportar_grupo_excel/<int:pk>/', views.exportar_cronograma_grupal_excel, name='exportar_cronograma_grupal_excel'),
    path('exportar_grupo_excel_pivot/<int:pk>/', views.exportar_cronograma_grupal_excel_pivot, name='exportar_cronograma_grupal_excel_pivot'),
    path('exportar_grupo_excel_pivot/<int:pk>/', views.exportar_cronograma_grupal_excel_pivot, name='exportar_cronograma_grupal_excel_pivot'),
    
    # Requisiciones Dashboard & Import
    path('requisiciones/dashboard/', views_import.requisicion_dashboard, name='requisicion_dashboard'),
    
    # Dashboard Views API (vistas personalizadas)
    path('requisiciones/dashboard/api/views/', views_dashboard_api.dashboard_views_list_create, name='dashboard_views_list_create'),
    path('requisiciones/dashboard/api/views/<int:pk>/delete/', views_dashboard_api.dashboard_view_delete, name='dashboard_view_delete'),
    path('requisiciones/dashboard/api/views/<int:pk>/apply/', views_dashboard_api.dashboard_view_apply, name='dashboard_view_apply'),
    path('requisiciones/dashboard/api/views/reset/', views_dashboard_api.dashboard_views_reset, name='dashboard_views_reset'),
    path('requisiciones/dashboard/api/detail/<uuid:pk>/', views_dashboard_api.requisicion_detail_api, name='requisicion_detail_api'),
    path('requisiciones/nuevo/', views_import.requisicion_upsert, name='requisicion_nuevo'),
    path('requisiciones/editar/<uuid:pk>/', views_import.requisicion_upsert, name='requisicion_editar'),
    path('requisiciones/<uuid:pk>/qr/', views_import.requisicion_qr, name='requisicion_qr'),
    path('requisiciones/<uuid:pk>/pdf/', views_import.requisicion_pdf, name='requisicion_pdf'),
    path('requisiciones/<uuid:pk>/docx/', views_import.requisicion_docx, name='requisicion_docx'),
    path('requisiciones/<uuid:pk>/unlock/', views_import.requisicion_unlock_edit, name='requisicion_unlock_edit'),
    path('requisiciones/<uuid:pk>/update-fecha-entrega/', views_import.api_update_fecha_entrega, name='api_update_requisicion_fecha_entrega'),
    path('requisiciones/autorizar/<uuid:pk>/', views_autorizar.requisicion_autorizar, name='requisicion_autorizar'),
    path('requisiciones/<uuid:pk>/notificar-recepcion/', views_import.notificar_recepcion, name='requisicion_notificar_recepcion'),
    path('requisiciones/<uuid:pk>/procesar/', views_import.procesar_requisicion, name='requisicion_procesar'),
    path('requisiciones/<uuid:pk>/finalizar-procesamiento/', views_import.finalizar_procesamiento, name='requisicion_finalizar_procesamiento'),
    path('requisiciones/<uuid:pk>/revertir-oc/', views_import.revertir_orden_compra, name='requisicion_revertir_oc'),
    path('requisiciones/<uuid:pk>/solicitar-informacion/', views_import.requisicion_solicitar_informacion, name='requisicion_solicitar_informacion'),
    path('requisiciones/<uuid:pk>/reenviar-informacion/', views_import.requisicion_reenviar_informacion, name='requisicion_reenviar_informacion'),
    path('ordenes-compra/<int:pk>/detalle/', views_import.detalle_orden_compra, name='orden_compra_detalle'),
    path('ordenes-compra/<int:pk>/actualizar/', views_import.actualizar_orden_compra, name='orden_compra_actualizar'),
    path('webhook/', views_webhook.requisicion_webhook_update, name='requisicion_webhook_update'),
    path('webhook/dynamics-sync/', views_webhook.dynamics_sync_webhook, name='dynamics_sync_webhook'),
    path('requisiciones/import-background/', views_import.import_requisiciones_background, name='import_requisiciones_background'),
    path('requisiciones/import-background/process/', views_import.import_requisiciones_process, name='import_requisiciones_process'),
    path('requisiciones/import-background/progress/', views_import.import_requisiciones_progress, name='import_requisiciones_progress'),
    path('requisiciones/import-background/template/', views_import.download_template, name='import_requisiciones_template'),
    path('requisiciones/import-json/', views_import.import_requisiciones_json, name='import_requisiciones_json'),
    path('requisiciones/import-json/trigger-cloud-sync/', views_import.trigger_power_automate_sync, name='trigger_cloud_sync'),
    path('api/partida/<int:partida_id>/items/', views_import.api_get_partida_items, name='api_get_partida_items'),
    
    # Pagos Dashboard
    path('pagos/dashboard/', views_pagos.dashboard_pagos, name='dashboard_pagos'),
    path('pagos/solicitud/<int:pk>/', views_pagos.detalle_solicitud_pago, name='detalle_solicitud_pago'),
    path('api/pagos/search-requisiciones/', views_pagos.api_search_requisiciones, name='api_search_requisiciones'),
    path('api/pagos/update-item/', views_pagos.api_update_item_pago, name='api_update_item_pago'),
    path('api/pagos/add-requisicion/', views_pagos.api_add_requisicion_pago, name='api_add_requisicion_pago'),
    path('api/pagos/delete-item/', views_pagos.api_delete_item_pago, name='api_delete_item_pago'),
    path('api/requisicion/<uuid:pk>/detalle/', views_pagos.api_requisicion_detalle, name='api_requisicion_detalle'),
    path('api/requisicion/<uuid:pk>/update-detalle/', views_pagos.api_update_requisicion_fields, name='api_update_requisicion_fields'),
    path('api/requisicion/<uuid:pk>/add-nota/', views_pagos.api_add_nota_requisicion, name='api_add_nota_requisicion'),
    path('api/requisicion/<uuid:pk>/notas/', views_pagos.api_get_notas_requisicion, name='api_get_notas_requisicion'),
    path('pagos/solicitud/<int:pk>/export/', views_pagos.exportar_solicitud_pago_excel, name='exportar_pago_excel'),
    path('pagos/solicitud/<int:pk>/import/', views_pagos.import_items_pago_background, name='import_items_pago'),
    path('api/pagos/import/process/', views_pagos.import_items_pago_process, name='import_items_pago_process'),
    path('api/pagos/import/progress/', views_pagos.import_items_pago_progress, name='import_items_pago_progress'),
    
    # Dashboard por Proveedor
    path('proveedores/dashboard/', views_pagos.dashboard_proveedores, name='dashboard_proveedores'),
    path('proveedores/<int:empresa_id>/detalle/', views_pagos.detalle_proveedor, name='detalle_proveedor'),
    
    # REPEX Dashboard
    path('repex/dashboard/', views_import.repex_dashboard, name='repex_dashboard'),
    
    # REPEX Cronograma / Visualizador
    path('repex/<int:pk>/', views.cronograma_repex, name='cronograma_repex'),
    path('api/repex/update-item/', views.api_update_repex_item, name='api_update_repex_item'),
    path('api/repex/update-item-apu/', views.api_update_repex_item_apu, name='api_update_repex_item_apu'),
    path('api/repex/add-item/', views.api_add_repex_item, name='api_add_repex_item'),
    path('api/repex/delete-item/', views.api_delete_repex_item, name='api_delete_repex_item'),
    path('api/repex/search-activos/', views.api_search_activos, name='api_search_activos'),
    path('api/repex/import-items/', views.api_import_repex_items, name='api_import_repex_items'),
    path('api/repex/add-manual-item/', views.api_add_manual_repex_item, name='api_add_manual_repex_item'),
    path('repex/<int:pk>/exportar/', views.exportar_repex_excel, name='exportar_repex_excel'),
    path('requisiciones/documento-proxy/<int:doc_id>/', views.requisicion_documento_proxy, name='requisicion_documento_proxy'),
    
    # API Selección Presupuesto
    path('api/requisicion/budget-selection-data/', views_pagos.api_get_budget_selection_data, name='api_get_budget_selection_data'),
    path('api/requisicion/update-budget/', views_pagos.api_requisicion_update_budget, name='api_requisicion_update_budget'),

    # Cotizaciones
    path('admin/cotizaciones/', views.lista_cotizaciones, name='lista_cotizaciones'),
    path('admin/cotizaciones/nueva/', views.crear_cotizacion, name='crear_cotizacion'),
    path('admin/cotizaciones/<int:pk>/', views.editar_cotizacion, name='editar_cotizacion'),
    path('admin/cotizaciones/<int:pk>/ver/', views.ver_cotizacion, name='ver_cotizacion'),
    path('admin/cotizaciones/<int:pk>/pdf/', views.cotizacion_pdf, name='cotizacion_pdf'),
    path('admin/cotizaciones/<int:pk>/excel/', views.cotizacion_excel, name='cotizacion_excel'),
    path('api/items-por-disciplina/<int:disciplina_id>/', views.api_items_por_disciplina, name='api_items_por_disciplina'),
    path('api/cotizaciones/<int:pk>/datos/', views.api_cotizacion_datos, name='api_cotizacion_datos'),
    path('api/cotizaciones/<int:pk>/guardar/', views.api_cotizacion_guardar, name='api_cotizacion_guardar'),

    # Catálogo de Artículos Predefinidos
    path('admin/catalogo/', views.lista_items_predefinidos, name='lista_items_predefinidos'),
    path('admin/catalogo/nuevo/', views.crear_item_predefinido, name='crear_item_predefinido'),
    path('admin/catalogo/<int:pk>/editar/', views.editar_item_predefinido, name='editar_item_predefinido'),
    path('admin/catalogo/<int:pk>/bom/', views.ver_bom, name='ver_bom'),

    # BOM API
    path('api/articulos/buscar/', views.api_buscar_articulos, name='api_buscar_articulos'),
    path('api/bom/<int:pk>/agregar/', views.bom_agregar_componente, name='bom_agregar_componente'),
    path('api/bom/<int:pk>/componente/<int:comp_pk>/eliminar/', views.bom_eliminar_componente, name='bom_eliminar_componente'),
    path('api/bom/<int:pk>/componente/<int:comp_pk>/actualizar/', views.bom_actualizar_componente, name='bom_actualizar_componente'),

    # Familias de Artículos
    path('admin/familias/', views.lista_familias, name='lista_familias'),
    path('admin/familias/nueva/', views.crear_familia, name='crear_familia'),
    path('admin/familias/<int:pk>/editar/', views.editar_familia, name='editar_familia'),

    # API Familias por disciplina (para selects dinámicos)
    path('api/familias-por-disciplina/<int:disciplina_id>/', views.api_familias_por_disciplina, name='api_familias_por_disciplina'),

    # Aliases para compatibilidad con URLs antiguas
    path('admin/items-predefinidos/', views.lista_items_predefinidos, name='lista_items_predefinidos_legacy'),
    path('admin/items-predefinidos/nuevo/', views.crear_item_predefinido, name='crear_item_predefinido_legacy'),
    path('admin/items-predefinidos/<int:pk>/editar/', views.editar_item_predefinido, name='editar_item_predefinido_legacy'),
    
    # Paquetes de Materiales
    path('admin/paquetes/', views_import.admin_paquetes_lista, name='admin_paquetes_lista'),
    path('admin/paquetes/nuevo/', views_import.admin_paquete_editar, name='admin_paquete_nuevo'),
    path('admin/paquetes/<int:pk>/', views_import.admin_paquete_editar, name='admin_paquete_editar'),
    path('api/paquetes/por-departamento/', views_import.api_paquetes_por_departamento, name='api_paquetes_por_departamento'),
    path('api/paquetes/<int:pk>/items/', views_import.api_paquete_items, name='api_paquete_items'),
    path('api/paquetes/<int:pk>/items/agregar/', views_import.api_paquete_agregar_item, name='api_paquete_agregar_item'),
    path('api/paquetes/<int:pk>/items/<int:item_id>/actualizar/', views_import.api_paquete_actualizar_item, name='api_paquete_actualizar_item'),
    path('api/paquetes/<int:pk>/items/<int:item_id>/eliminar/', views_import.api_paquete_eliminar_item, name='api_paquete_eliminar_item'),
    path('api/paquetes/<int:pk>/exportar/', views_import.api_paquete_exportar, name='api_paquete_exportar'),
    path('api/paquetes/exportar/progress/', views_import.api_paquete_exportar_progress, name='api_paquete_exportar_progress'),
    path('api/paquetes/<int:pk>/importar/', views_import.api_paquete_importar, name='api_paquete_importar'),
    path('api/paquetes/importar/progress/', views_import.api_paquete_importar_progress, name='api_paquete_importar_progress'),
    path('api/paquetes/descargar-template/', views_import.api_paquete_descargar_template, name='api_paquete_descargar_template'),

    # Partida Presupuestaria - Admin Fiori
    path('partidas/admin/', views.partida_admin_fiori, name='partida_admin_fiori'),
    path('api/partidas/admin/', views.partida_admin_api, name='partida_admin_api'),

    # Códigos de Exoneración - Importación
    path('codigos-exoneracion/import/', views_import.import_codigos_exoneracion_view, name='import_codigos_exoneracion'),
    path('codigos-exoneracion/import/process/', views_import.import_codigos_exoneracion_process, name='import_codigos_exoneracion_process'),
    path('codigos-exoneracion/import/progress/', views_import.import_codigos_exoneracion_progress, name='import_codigos_exoneracion_progress'),
    path('api/codigos-exoneracion/create/', views_import.api_create_codigo_exoneracion, name='api_create_codigo_exoneracion'),
    path('api/codigos-exoneracion/<int:pk>/detalle/', views_import.api_detalle_codigo_exoneracion, name='api_detalle_codigo_exoneracion'),
    path('api/codigos-exoneracion/add-material/', views_import.api_add_material_exoneracion, name='api_add_material_exoneracion'),
    path('api/codigos-exoneracion/remove-material/', views_import.api_remove_material_exoneracion, name='api_remove_material_exoneracion'),
    path('api/codigos-exoneracion/update-material/', views_import.api_update_material_exoneracion, name='api_update_material_exoneracion'),
]
