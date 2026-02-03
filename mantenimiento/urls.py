from django.urls import path
from . import views
from .views import import_rutinas
from .views.rutinas_dashboard import rutinas_dashboard, rutina_detail_api, rutina_save_api, rutina_delete_api, procedimiento_save_api, procedimiento_detail_api

app_name = 'mantenimiento'

urlpatterns = [
    path('calendario/', views.calendario_mantenimiento, name='calendario'),
    path('calendario/detallado/', views.calendario_detallado, name='detallado'),
    path('cronograma/', views.cronograma_mantenimiento_visual, name='cronograma'),
    path('cronograma/wizard/', views.wizard_cronograma, name='cronograma_wizard'),
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
    path('app/ot/<int:pk>/iniciar/', views.mobile_ot_iniciar, name='mobile_ot_iniciar'),
    path('app/ot/<int:pk>/finalizar/', views.mobile_ot_finalizar, name='mobile_ot_finalizar'),
    path('app/aviso/crear/', views.mobile_crear_aviso, name='mobile_crear_aviso'),
    path('app/aviso/<int:pk>/', views.mobile_aviso_detalle, name='mobile_aviso_detalle'),
    path('app/avisos/', views.mobile_mis_avisos, name='mobile_mis_avisos'),
    path('app/crear-ot-rutina/<int:rutina_id>/', views.mobile_crear_ot_rutina, name='mobile_crear_ot_rutina'),
    path('dashboard-cargas/', views.dashboard_cargas, name='dashboard_cargas'),
    path('rutinas/dashboard/', rutinas_dashboard, name='rutinas_dashboard'),
    path('rutinas/dashboard/detail/<int:pk>/', rutina_detail_api, name='rutina_detail_api'),
    path('rutinas/dashboard/save/', rutina_save_api, name='rutina_save_api'),
    path('rutinas/dashboard/delete/<int:pk>/', rutina_delete_api, name='rutina_delete_api'),
    path('rutinas/dashboard/procedimiento/save/', procedimiento_save_api, name='procedimiento_save_api'),
    path('rutinas/dashboard/procedimiento/detail/<int:pk>/', procedimiento_detail_api, name='procedimiento_detail_api'),
    path('proyeccion-generar/api/', views.api_generar_orden_individual, name='api_generar_orden_individual'),

    # Importación de Rutinas (Aislada)
    path('import-rutinas/', import_rutinas.import_rutinas_background, name='rutina_import_background'),
    path('import-rutinas/process/', import_rutinas.import_rutinas_process, name='rutina_import_process'),
    path('import-rutinas/progress/', import_rutinas.import_rutinas_progress, name='rutina_import_progress'),
]
