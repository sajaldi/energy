from django.urls import path
from . import views, views_import, views_autorizar, views_webhook, views_mayan, views_pagos

app_name = 'presupuestos'

urlpatterns = [
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
    
    # Requisiciones Dashboard & Import
    path('requisiciones/dashboard/', views_import.requisicion_dashboard, name='requisicion_dashboard'),
    path('requisiciones/nuevo/', views_import.requisicion_upsert, name='requisicion_nuevo'),
    path('requisiciones/editar/<uuid:pk>/', views_import.requisicion_upsert, name='requisicion_editar'),
    path('requisiciones/autorizar/<uuid:pk>/', views_autorizar.requisicion_autorizar, name='requisicion_autorizar'),
    path('api/requisicion/webhook/update/', views_webhook.requisicion_webhook_update, name='requisicion_webhook_update'),
    path('requisiciones/import-background/', views_import.import_requisiciones_background, name='import_requisiciones_background'),
    path('requisiciones/import-background/process/', views_import.import_requisiciones_process, name='import_requisiciones_process'),
    path('requisiciones/import-background/progress/', views_import.import_requisiciones_progress, name='import_requisiciones_progress'),
    path('requisiciones/import-background/template/', views_import.download_template, name='import_requisiciones_template'),
    
    # Pagos Dashboard
    path('pagos/dashboard/', views_pagos.dashboard_pagos, name='dashboard_pagos'),
    path('pagos/solicitud/<int:pk>/', views_pagos.detalle_solicitud_pago, name='detalle_solicitud_pago'),
    path('api/pagos/update-item/', views_pagos.api_update_item_pago, name='api_update_item_pago'),
    path('api/pagos/add-requisicion/', views_pagos.api_add_requisicion_pago, name='api_add_requisicion_pago'),
    
    # Mayan Integration
    path('api/mayan/upload-requisition-document/', views_mayan.upload_requisition_document_to_mayan, name='mayan_upload_requisition_document'),
]
