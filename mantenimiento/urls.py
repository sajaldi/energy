from django.urls import path
from . import views
from .views import import_rutinas, import_pasos
from .views.rutinas_dashboard import (
    rutinas_dashboard, rutina_detail_api, rutina_save_api, 
    rutina_delete_api, rutina_delete_secure_api, rutina_pasos_save_api, rutina_qr_pdf,
    api_rutina_kpis, api_rutina_kpis_save,
    paso_media_upload_api, paso_media_delete_api,
    rutina_print_pdf, rutina_move_api, tipo_move_api,
    export_rutinas_excel, rutina_reporte_html
)
from .views import asistencia

app_name = 'mantenimiento'

urlpatterns = [
    path('', views.mantenimiento_dashboard, name='dashboard'),
    path('ordenes/', views.ordenes_lista_view, name='ordenes_lista'),
    path('ordenes/bulk-delete/', views.ordenes_bulk_delete, name='ordenes_bulk_delete'),
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
    path('app/ot/<int:pk>/vincular-activo/', views.mobile_ot_vincular_activo, name='mobile_ot_vincular_activo'),
    path('app/ot/<int:pk>/iniciar/', views.mobile_ot_iniciar, name='mobile_ot_iniciar'),
    path('app/ot/<int:pk>/finalizar/', views.mobile_ot_finalizar, name='mobile_ot_finalizar'),
    path('app/ot/<int:pk>/eliminar/', views.mobile_ot_eliminar, name='mobile_ot_eliminar'),
    path('app/ot/<int:pk>/upload-file/', views.mobile_ot_upload_file, name='mobile_ot_upload_file'),
    path('app/ot/<int:pk>/delete-file/<int:archivo_id>/', views.mobile_ot_delete_file, name='mobile_ot_delete_file'),
    path('app/ot/<int:ot_id>/update-file-name/<int:file_id>/', views.mobile_ot_update_file_name, name='mobile_ot_update_file_name'),
    path('app/ot/<int:pk>/send-webhook/', views.mobile_ot_webhook, name='mobile_ot_webhook'),
    path('app/ot/<int:pk>/send-whatsapp/', views.mobile_ot_whatsapp_webhook, name='mobile_ot_whatsapp_webhook'),
    path('app/aviso/crear/', views.mobile_crear_aviso, name='mobile_crear_aviso'),
    path('app/aviso/<int:pk>/editar/', views.mobile_aviso_editar, name='mobile_aviso_editar'),
    path('fiori/aviso/<int:pk>/', views.aviso_fiori_view, name='aviso_fiori'),
    path('app/aviso/<int:pk>/', views.mobile_aviso_detalle, name='mobile_aviso_detalle'),
    path('app/avisos/', views.mobile_mis_avisos, name='mobile_mis_avisos'),
    path('app/ordenes/', views.mobile_mis_ordenes, name='mobile_mis_ordenes'),
    path('app/crear-ot-rutina/<int:rutina_id>/', views.mobile_crear_ot_rutina, name='mobile_crear_ot_rutina'),
    path('app/ot/crear-desde-puesto/', views.mobile_crear_ot_desde_puesto, name='mobile_crear_ot_desde_puesto'),
    path('app/medicion/<int:pk>/crear/', views.mobile_crear_medicion, name='mobile_crear_medicion'),
    path('app/ot/<int:pk>/check-pdf-status/', views.check_ot_pdf_status, name='check_ot_pdf_status'),
    path('app/ot/crear-no-programada/', views.mobile_crear_otnp, name='mobile_crear_otnp'),
    path('dashboard-cargas/', views.dashboard_cargas, name='dashboard_cargas'),
    path('dashboard-cargas/asignar-puesto/', views.asignar_puesto_ajax, name='asignar_puesto_ajax'),
    path('rutinas/dashboard/', rutinas_dashboard, name='rutinas_dashboard'),
    path('rutinas/dashboard/detail/<int:pk>/', rutina_detail_api, name='rutina_detail_api'),
    path('rutinas/dashboard/qr/<int:pk>/', rutina_qr_pdf, name='rutina_qr_pdf'),
    path('rutinas/dashboard/print/<int:pk>/', rutina_print_pdf, name='rutina_print_pdf'),
    path('rutinas/dashboard/save/', rutina_save_api, name='rutina_save_api'),
    path('rutinas/dashboard/delete/<int:pk>/', rutina_delete_api, name='rutina_delete_api'),
    path('rutinas/dashboard/delete-secure/<int:pk>/', rutina_delete_secure_api, name='rutina_delete_secure_api'),
    path('rutinas/dashboard/move/<int:pk>/', rutina_move_api, name='rutina_move_api'),
    path('rutinas/dashboard/rutina/pasos/save/', rutina_pasos_save_api, name='rutina_pasos_save_api'),
    path('rutinas/dashboard/rutina/<int:pk>/kpis/', api_rutina_kpis, name='api_rutina_kpis'),
    path('rutinas/dashboard/rutina/<int:pk>/kpis/save/', api_rutina_kpis_save, name='api_rutina_kpis_save'),
    # Media de Pasos de Rutina
    path('rutinas/dashboard/paso/<int:paso_id>/media/upload/', paso_media_upload_api, name='paso_media_upload_api'),
    path('rutinas/dashboard/paso/media/<int:media_id>/delete/', paso_media_delete_api, name='paso_media_delete_api'),
    # API Endpoints para Tipos (Categorías) dentro del dashboard
    path('rutinas/api/tipo/<int:pk>/', views.rutinas_dashboard.tipo_detail_api, name='tipo_detail_api'),
    path('rutinas/api/tipo/save/', views.rutinas_dashboard.tipo_save_api, name='tipo_save_api'),
    path('rutinas/api/tipo/<int:pk>/delete/', views.rutinas_dashboard.tipo_delete_api, name='tipo_delete_api'),
    path('rutinas/api/tipo/<int:pk>/kpis/', views.rutinas_dashboard.api_tipo_kpis, name='api_tipo_kpis'),
    path('rutinas/api/tipo/<int:pk>/kpis/save/', views.rutinas_dashboard.api_tipo_kpis_save, name='api_tipo_kpis_save'),
    path('rutinas/api/tipo/move/<int:pk>/', tipo_move_api, name='tipo_move_api'),
    path('rutinas/export-excel/', export_rutinas_excel, name='export_rutinas_excel'),
    path('rutinas/<int:pk>/reporte/', rutina_reporte_html, name='rutina_reporte_html'),
    path('proyeccion-generar/api/', views.api_generar_orden_individual, name='api_generar_orden_individual'),

    # Importación de Rutinas (Aislada)
    path('import-rutinas/', import_rutinas.import_rutinas_background, name='rutina_import_background'),
    path('import-rutinas/process/', import_rutinas.import_rutinas_process, name='rutina_import_process'),
    path('import-rutinas/progress/', import_rutinas.import_rutinas_progress, name='rutina_import_progress'),
    
    # Importación de Pasos de Rutina
    path('import-pasos/', import_pasos.import_pasos_background, name='pasorutina_import_background'),
    path('import-pasos/process/', import_pasos.import_pasos_process, name='pasorutina_import_process'),
    path('import-pasos/progress/', import_pasos.import_pasos_progress, name='pasorutina_import_progress'),
    path('import-pasos/template/', import_pasos.download_pasos_template, name='pasorutina_download_template'),

    # Importación de Tipos (Mantenimiento)
    path('import-tipos/', views.import_categorias.import_categorias_background, name='tipo_import_background'),
    path('import-tipos/process/', views.import_categorias.import_categorias_process, name='tipo_import_process'),
    path('import-tipos/progress/', views.import_categorias.import_categorias_progress, name='tipo_import_progress'),
    path('import-tipos/template/', views.import_categorias.download_categorias_template, name='tipo_download_template'),

    # Buscador Inteligente con IA
    path('cronograma/buscador-ia/', views.buscador_ia_cronograma, name='buscador_ia'),
    path('api/busqueda-ia/', views.api_busqueda_ia, name='api_busqueda_ia'),

    path('api/search-ordenes/', views.api_search_ordenes, name='api_search_ordenes'),
    path('api/busqueda-global/', views.api_busqueda_global, name='api_busqueda_global'),
    path('api/ot/<int:pk>/detalle/', views.api_get_ot_detail, name='api_get_ot_detail'),
    path('api/ot/<int:pk>/related/', views.api_get_ot_related, name='api_get_ot_related'),
    path('api/ot/<int:pk>/update/', views.api_update_ot_status_notes, name='api_update_ot_status_notes'),
    path('api/foto/<int:pk>/update-descripcion/', views.api_update_foto_descripcion, name='api_update_foto_descripcion'),
    path('api/search-activos/', views.api_buscar_activos, name='api_buscar_activos'),
    path('api/search-activos-filtrados/', views.api_buscar_activos_filtrados, name='api_buscar_activos_filtrados'),
    path('api/ordenes-hoy/', views.api_ordenes_hoy, name='api_ordenes_hoy'),
    path('api/cerrar-ot/<int:pk>/', views.api_cerrar_ot, name='api_cerrar_ot'),
    path('api/guardar-cierre/<int:pk>/', views.api_guardar_cierre, name='api_guardar_cierre'),
    path('rutina-pdf/<int:ot_id>/', views.pdf_views.generate_rutina_pdf_view, name='rutina_pdf'),
    path('aviso-pdf/<int:aviso_id>/', views.pdf_views.generate_aviso_pdf_view, name='aviso_pdf'),

    # Asistencia
    path('asistencia/estacion/', asistencia.AsistenciaStationView.as_view(), name='asistencia_estacion'),
    path('asistencia/procesar/', asistencia.AsistenciaProcessView.as_view(), name='asistencia_procesar'),
    path('asistencia/reporte/', asistencia.AsistenciaReportView.as_view(), name='asistencia_reporte'),
    path('asistencia/buscar-sin-vincular/', asistencia.BuscarTecnicosSinVincularView.as_view(), name='asistencia_buscar_sin_vincular'),
    path('asistencia/vincular/', asistencia.VincularTecnicoCodigoView.as_view(), name='asistencia_vincular'),
    path('asistencia/en-vivo/', asistencia.AsistenciaEnVivoView.as_view(), name='asistencia_en_vivo'),
    path('asistencia/gestor/buscar/', asistencia.BuscarPersonalGestorView.as_view(), name='asistencia_buscar_personal'),
    path('asistencia/gestor/guardar/', asistencia.GestionarPersonalView.as_view(), name='asistencia_gestionar_personal'),

    # Avisos Dashboard Kanban
    path('avisos/dashboard/', views.avisos_dashboard.avisos_kanban_dashboard, name='avisos_dashboard'),
    path('avisos/api/list/', views.avisos_dashboard.api_get_avisos, name='api_get_avisos'),
    path('avisos/api/update/<int:pk>/', views.avisos_dashboard.api_update_aviso_estado, name='api_update_aviso_estado'),
    path('avisos/api/create-ot/<int:pk>/', views.avisos_dashboard.api_aviso_create_ot, name='api_aviso_create_ot'),
    path('avisos/api/notify/<int:pk>/', views.avisos_dashboard.api_notify_responsable, name='api_notify_responsable'),
]
