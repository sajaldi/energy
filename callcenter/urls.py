from django.urls import path
from . import views

app_name = 'callcenter'

urlpatterns = [
    path('webhook-new-ticket/', views.webhook_new_ticket, name='webhook_new_ticket'),
    path('api/ticket/<str:folio>/pdf/', views.generate_ticket_pdf_view, name='generate_ticket_pdf'),
    path('api/ticket/<str:folio>/upload_evidencia/', views.webhook_evidencia_ticket, name='webhook_evidencia_ticket'),
    path('ticket/<str:ticket_id>/enviar-power-automate/', views.send_ticket_to_power_automate_view, name='send_power_automate'),
    path('buscar/', views.ticket_search_view, name='buscar_tickets'),
    
    # Visual Closure Interface
    path('dashboard/', views.ticket_dashboard_view, name='ticket_dashboard'),
    path('wizard-cluster/', views.wizard_cluster_view, name='wizard_cluster'),
    path('dashboard/cluster/<str:cluster_id>/', views.cluster_tickets_view, name='cluster_tickets'),
    path('dashboard/cluster/<str:cluster_id>/bulk-update/', views.bulk_update_tickets_api, name='cluster_bulk_update'),
    path('dashboard/node-tickets/', views.get_dashboard_node_tickets_ajax, name='dashboard_node_tickets'),
    path('ticket/<str:ticket_id>/cierre-visual/', views.ticket_cierre_visual_view, name='ticket_cierre_visual'),
    path('ticket/<str:ticket_id>/upload-evidencia/', views.upload_evidencia_ajax, name='upload_evidencia_visual'),
    path('evidencia/<int:evidencia_id>/analizar-ia/', views.analyze_evidence_ai_ajax, name='analyze_evidence_ia'),
    path('ticket/<str:ticket_id>/delete-evidencia/<int:evidencia_id>/', views.delete_evidencia_ajax, name='delete_evidencia_visual'),
    path('update-descripcion-evidencia/<int:evidence_id>/', views.update_evidencia_descripcion_ajax, name='update_evidencia_descripcion_ajax'),
    path('search-activos/', views.search_activos_ajax, name='search_activos_ajax'),
    path('ticket/<str:ticket_id>/update-activo/', views.update_ticket_activo_ajax, name='update_ticket_activo_ajax'),
    path('get-assignable-users/', views.get_assignable_users_ajax, name='get_assignable_users'),
    path('ticket/<str:ticket_id>/assign-user/', views.assign_ticket_user_ajax, name='assign_ticket_user'),
    path('ticket/<str:ticket_id>/update-deductiva/', views.update_ticket_deductiva_ajax, name='update_ticket_deductiva'),
    path('ticket/<str:ticket_id>/notify-n8n/', views.notify_ticket_n8n_ajax, name='notify_ticket_n8n'),
    path('cluster/<str:cluster_id>/create-ticket/', views.create_ticket_in_cluster_ajax, name='create_ticket_in_cluster'),
    path('cluster/<str:cluster_id>/add-tickets-folios/', views.add_tickets_to_cluster_ajax, name='add_tickets_to_cluster_folios'),
    path('cluster/<str:cluster_id>/vectorizar-ia/', views.vectorize_cluster_tickets_ajax, name='vectorizar_ia_cluster'),
    path('cluster/<str:cluster_id>/import-deductivas/', views.import_deductivas_excel_ajax, name='import_deductivas_excel'),
    path('template-deductivas/', views.download_deductivas_template, name='download_deductivas_template'),
    path('api/search-tickets-autocomplete/', views.search_tickets_autocomplete_ajax, name='search_tickets_autocomplete'),
    path('ticket/<str:ticket_id>/restriccion-acceso/', views.create_restriccion_acceso_ajax, name='create_restriccion_acceso_ajax'),
    path('ticket/<str:ticket_id>/comentario-interno/', views.save_comentario_interno_ajax, name='save_comentario_interno_ajax'),
    path('ticket/<str:ticket_id>/toggle-interno/', views.toggle_ticket_interno_ajax, name='toggle_ticket_interno_ajax'),
    path('ajax/get-diagnosticos-by-falla/', views.get_diagnosticos_by_falla_ajax, name='get_diagnosticos_by_falla_ajax'),
    path('ticket/<str:ticket_id>/detail-ajax/', views.ticket_detail_ajax, name='ticket_detail_ajax'),
    path('ticket/<str:ticket_id>/quick-edit/', views.ticket_quick_edit_ajax, name='ticket_quick_edit_ajax'),
    path('restriccion-acceso/<int:pk>/pdf/', views.export_restriccion_acceso_pdf, name='export_restriccion_acceso_pdf'),
    path('api/webhook/correo-cierre-callback/', views.webhook_correo_cierre_callback, name='webhook_correo_cierre_callback'),
    path('ticket/<str:ticket_id>/verify-correo-cierre/', views.verify_correo_cierre_ajax, name='verify_correo_cierre'),
    path('app/ticket/<int:pk>/', views.mobile_ticket_detalle_view, name='mobile_ticket_detalle'),
    path('ticket/<str:ticket_id>/exportar-pdf/', views.exportar_solicitudticket_pdf, name='exportar_solicitudticket_pdf'),
    
    # Tiempo Acordado Module
    path('tiempo-acordado/dashboard/', views.tiempo_acordado_dashboard_view, name='tiempo_acordado_dashboard'),
    path('app/tiempo-acordado/nuevo/', views.mobile_crear_tiempo_acordado_view, name='mobile_crear_tiempo_acordado'),
    path('app/tiempo-acordado/<int:pk>/', views.mobile_detalle_tiempo_acordado_view, name='mobile_detalle_tiempo_acordado'),
    path('app/tiempo-acordado/<int:pk>/editar/', views.mobile_crear_tiempo_acordado_view, name='mobile_editar_tiempo_acordado'),
    path('app/tiempo-acordado/<int:pk>/pdf/', views.exportar_tiempo_acordado_pdf_view, name='exportar_tiempo_acordado_pdf'),
    path('app/tiempo-acordado/<int:pk>/enviar/', views.enviar_tiempo_acordado_power_automate_ajax, name='enviar_tiempo_acordado_power_automate'),
    
    # API para Búsqueda
    path('api/enlace/<int:enlace_id>/details/', views.get_enlace_details_ajax, name='enlace_details_ajax'),
    path('api/ubicacion/<int:parent_id>/sububicaciones/', views.api_get_sububicaciones_ajax, name='api_get_sububicaciones'),
    path('api/search-enlaces-autocomplete/', views.api_busqueda_enlaces_ajax, name='search_enlaces_autocomplete'),

    # Enlaces (Contactos) Interface
    path('enlaces/', views.enlaces_lista_view, name='enlaces_lista'),
    
    # Cronogramas Predefinidos (Templates)
    path('cronogramas-predefinidos/', views.cronograma_predefinido_lista_view, name='callcenter_cronogramas_lista'),
    path('cronogramas-predefinidos/nuevo/', views.cronograma_predefinido_edit_view, name='callcenter_cronograma_nuevo'),
    path('cronogramas-predefinidos/<int:pk>/', views.cronograma_predefinido_detalle_view, name='callcenter_cronograma_detalle'),
    path('cronogramas-predefinidos/<int:pk>/editar/', views.cronograma_predefinido_edit_view, name='callcenter_cronograma_editar'),
    path('api/cronograma-predefinido/<int:pk>/items/', views.api_get_cronograma_items_ajax, name='api_get_cronograma_items_ajax'),
    path('api/webhook/vector-update/', views.webhook_ticket_vector_callback, name='webhook_ticket_vector_callback'),
    path('app/ticket/new-cierre/<int:pk>/', views.mobile_ticket_cierre_view, name='mobile_ticket_cierre'),
    path('cluster/create-manual-ajax/', views.create_cluster_manual_ajax, name='create_cluster_manual_ajax'),
    path('sync-sig/', views.trigger_sync_dashboard, name='trigger_sync_dashboard'),
    
    # Dashboard Público (auto-refresh, sin login)
    path('tickets_dashboard/', views.tickets_dashboard_public_view, name='tickets_dashboard_public'),
    path('tickets_dashboard/api/', views.tickets_dashboard_api, name='tickets_dashboard_api'),
    path('tickets_dashboard/command/', views.tickets_dashboard_command, name='tickets_dashboard_command'),
    path('dashboard_config/', views.dashboard_config_view, name='dashboard_config'),
    path('dashboard_config/api/clusters/', views.dashboard_config_clusters_api, name='dashboard_config_clusters_api'),
    path('dashboard_control/', views.dashboard_control_view, name='dashboard_control'),
    
    # Dashboard Instituciones
    path('instituciones/dashboard/', views.instituciones_dashboard_view, name='instituciones_dashboard'),
    path('instituciones/api/<int:pk>/', views.institucion_detail_api, name='institucion_detail_api'),
    path('instituciones/api/<int:pk>/fallas/', views.institucion_fallas_por_servicio_api, name='institucion_fallas_api'),

    # Vista pública de adjuntos del ticket (accesible desde correo)
    path('ticket/<str:ticket_id>/adjuntos/', views.ticket_adjuntos_public_view, name='ticket_adjuntos_public'),
    
    # API departamentos con responsable (para reasignación)
    path('api/departamentos-responsables/', views.get_departamentos_responsables_ajax, name='get_departamentos_responsables'),
    path('ticket/<str:ticket_id>/reasignar-departamento/', views.reasignar_ticket_departamento_ajax, name='reasignar_ticket_departamento'),
]

