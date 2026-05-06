from django.urls import path
from . import views, views_import, views_autorizar, views_webhook, views_pagos

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
    path('exportar_excel/<int:pk>/', views.exportar_cronograma_excel, name='exportar_excel'),
    path('exportar_pdf/<int:pk>/', views.exportar_cronograma_pdf, name='exportar_pdf'),
    path('exportar_grupo_pdf/<int:pk>/', views.exportar_cronograma_grupal_pdf, name='exportar_cronograma_grupal_pdf'),
    path('exportar_grupo_excel/<int:pk>/', views.exportar_cronograma_grupal_excel, name='exportar_cronograma_grupal_excel'),
    path('exportar_grupo_excel_pivot/<int:pk>/', views.exportar_cronograma_grupal_excel_pivot, name='exportar_cronograma_grupal_excel_pivot'),
    path('exportar_grupo_excel_pivot/<int:pk>/', views.exportar_cronograma_grupal_excel_pivot, name='exportar_cronograma_grupal_excel_pivot'),
    
    # Requisiciones Dashboard & Import
    path('requisiciones/dashboard/', views_import.requisicion_dashboard, name='requisicion_dashboard'),
    path('requisiciones/nuevo/', views_import.requisicion_upsert, name='requisicion_nuevo'),
    path('requisiciones/editar/<uuid:pk>/', views_import.requisicion_upsert, name='requisicion_editar'),
    path('requisiciones/<uuid:pk>/qr/', views_import.requisicion_qr, name='requisicion_qr'),
    path('requisiciones/<uuid:pk>/pdf/', views_import.requisicion_pdf, name='requisicion_pdf'),
    path('requisiciones/<uuid:pk>/unlock/', views_import.requisicion_unlock_edit, name='requisicion_unlock_edit'),
    path('requisiciones/autorizar/<uuid:pk>/', views_autorizar.requisicion_autorizar, name='requisicion_autorizar'),
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
    path('api/requisicion/<uuid:pk>/update-comentarios/', views_pagos.api_update_requisicion_comentarios, name='api_update_requisicion_comentarios'),
    path('pagos/solicitud/<int:pk>/export/', views_pagos.exportar_solicitud_pago_excel, name='exportar_pago_excel'),
    path('pagos/solicitud/<int:pk>/import/', views_pagos.import_items_pago_background, name='import_items_pago'),
    path('api/pagos/import/process/', views_pagos.import_items_pago_process, name='import_items_pago_process'),
    path('api/pagos/import/progress/', views_pagos.import_items_pago_progress, name='import_items_pago_progress'),
    
    # Dashboard por Proveedor
    path('proveedores/dashboard/', views_pagos.dashboard_proveedores, name='dashboard_proveedores'),
    path('proveedores/<int:empresa_id>/detalle/', views_pagos.detalle_proveedor, name='detalle_proveedor'),
    
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
]
