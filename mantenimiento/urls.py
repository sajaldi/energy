from django.urls import path
from . import views
from .views import import_rutinas
from .views.rutinas_dashboard import rutinas_dashboard, rutina_detail_api, rutina_save_api, rutina_delete_api, rutina_pasos_save_api

app_name = 'mantenimiento'

urlpatterns = [
    path('', views.mantenimiento_dashboard, name='dashboard'),
    path('calendario/', views.calendario_mantenimiento, name='calendario'),
    path('calendario/detallado/', views.calendario_detallado, name='detallado'),
    path('cronograma/', views.cronograma_mantenimiento_visual, name='cronograma'),
    path('cronograma/wizard/', views.wizard_cronograma, name='cronograma_wizard'),
    path('cronograma/wizard-mensual/', views.wizard_mensual, name='wizard_mensual'),
    path('cronograma/matriz-mensual/', views.cronograma_mensual_matriz, name='cronograma_mensual_matriz'),
    path('cronograma/<int:year>/<int:month>/', views.detalle_mes, name='detalle_mes'),
    path('api/update-ot-date/', views.api_update_ot_date, name='api_update_ot_date'),
    path('api/split-ot-asset/', views.api_split_ot_asset, name='api_split_ot_asset'),
    path('api/merge-ots/', views.api_merge_ots, name='api_merge_ots'),
    path('api/bulk-update-ot-dates/', views.api_bulk_update_ot_dates, name='api_bulk_update_ot_dates'),
    path('api/delete-ots/', views.api_delete_ots, name='api_delete_ots'),
    path('api/notifications/', views.api_get_notifications, name='api_get_notifications'),
    path('api/notifications/read/', views.api_mark_notification_read, name='api_mark_notification_read'),
    path('programar-rutina/', views.programar_rutina_wizard, name='programar_rutina_wizard'),
    path('api/get-assets-wizard/', views.api_get_assets_wizard, name='api_get_assets_wizard'),
    path('app/cronograma/', views.mobile_cronograma, name='mobile_cronograma'),
    path('api/programacion/<int:pk>/detalle/', views.mobile_programacion_detalle, name='mobile_programacion_detalle'),
    
    # Proyecciones
    path('proyeccion/<int:pk>/', views.visualizador_proyecciones, name='visualizador_proyecciones'),
    path('proyeccion-generar/<int:pk>/', views.generar_ordenes_programacion, name='generar_ordenes_programacion'),
    path('app/ot/<int:pk>/', views.mobile_ot_detalle, name='mobile_ot_detalle'),
    path('app/ot/<int:pk>/update-ajax/', views.mobile_ot_update_ajax, name='mobile_ot_update_ajax'),
    path('app/ot/<int:pk>/iniciar/', views.mobile_ot_iniciar, name='mobile_ot_iniciar'),
    path('app/ot/<int:pk>/finalizar/', views.mobile_ot_finalizar, name='mobile_ot_finalizar'),
    path('app/ot/<int:pk>/upload-file/', views.mobile_ot_upload_file, name='mobile_ot_upload_file'),
    path('app/ot/<int:pk>/delete-file/<int:archivo_id>/', views.mobile_ot_delete_file, name='mobile_ot_delete_file'),
    path('app/aviso/crear/', views.mobile_crear_aviso, name='mobile_crear_aviso'),
    path('app/aviso/<int:pk>/', views.mobile_aviso_detalle, name='mobile_aviso_detalle'),
    path('app/avisos/', views.mobile_mis_avisos, name='mobile_mis_avisos'),
    path('app/crear-ot-rutina/<int:rutina_id>/', views.mobile_crear_ot_rutina, name='mobile_crear_ot_rutina'),
    path('dashboard-cargas/', views.dashboard_cargas, name='dashboard_cargas'),
    path('rutinas/dashboard/', rutinas_dashboard, name='rutinas_dashboard'),
    path('rutinas/dashboard/detail/<int:pk>/', rutina_detail_api, name='rutina_detail_api'),
    path('rutinas/dashboard/save/', rutina_save_api, name='rutina_save_api'),
    path('rutinas/dashboard/delete/<int:pk>/', rutina_delete_api, name='rutina_delete_api'),
    path('rutinas/dashboard/rutina/pasos/save/', rutina_pasos_save_api, name='rutina_pasos_save_api'),
    # API Endpoints para Tipos (Categorías) dentro del dashboard
    path('rutinas/api/tipo/<int:pk>/', views.rutinas_dashboard.tipo_detail_api, name='tipo_detail_api'),
    path('rutinas/api/tipo/save/', views.rutinas_dashboard.tipo_save_api, name='tipo_save_api'),
    path('rutinas/api/tipo/<int:pk>/delete/', views.rutinas_dashboard.tipo_delete_api, name='tipo_delete_api'),
    path('proyeccion-generar/api/', views.api_generar_orden_individual, name='api_generar_orden_individual'),

    # Importación de Rutinas (Aislada)
    path('import-rutinas/', import_rutinas.import_rutinas_background, name='rutina_import_background'),
    path('import-rutinas/process/', import_rutinas.import_rutinas_process, name='rutina_import_process'),
    path('import-rutinas/progress/', import_rutinas.import_rutinas_progress, name='rutina_import_progress'),
    # Importación de Procedimientos fue removida porque ahora son Pasos de Rutina

    # Importación de Tipos (Mantenimiento)
    path('import-tipos/', views.import_categorias.import_categorias_background, name='tipo_import_background'),
    path('import-tipos/process/', views.import_categorias.import_categorias_process, name='tipo_import_process'),
    path('import-tipos/progress/', views.import_categorias.import_categorias_progress, name='tipo_import_progress'),
    path('import-tipos/template/', views.import_categorias.download_categorias_template, name='tipo_download_template'),

    path('api/search-ordenes/', views.api_search_ordenes, name='api_search_ordenes'),
    path('api/ot/<int:pk>/detalle/', views.api_get_ot_detail, name='api_get_ot_detail'),
    path('api/ot/<int:pk>/update/', views.api_update_ot_status_notes, name='api_update_ot_status_notes'),
    path('api/search-activos/', views.api_buscar_activos, name='api_buscar_activos'),
    path('rutina-pdf/<int:ot_id>/', views.pdf_views.generate_rutina_pdf_view, name='rutina_pdf'),
]
