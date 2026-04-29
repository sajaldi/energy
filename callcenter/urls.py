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
    path('ticket/<str:ticket_id>/cierre-visual/', views.ticket_cierre_visual_view, name='ticket_cierre_visual'),
    path('ticket/<str:ticket_id>/upload-evidencia/', views.upload_evidencia_ajax, name='upload_evidencia_visual'),
    path('ticket/<str:ticket_id>/delete-evidencia/<int:evidencia_id>/', views.delete_evidencia_ajax, name='delete_evidencia_visual'),
    path('update-descripcion-evidencia/<int:evidence_id>/', views.update_evidencia_descripcion_ajax, name='update_evidencia_descripcion_ajax'),
    path('search-activos/', views.search_activos_ajax, name='search_activos_ajax'),
    path('ticket/<str:ticket_id>/update-activo/', views.update_ticket_activo_ajax, name='update_ticket_activo_ajax'),
    path('get-assignable-users/', views.get_assignable_users_ajax, name='get_assignable_users'),
    path('ticket/<str:ticket_id>/assign-user/', views.assign_ticket_user_ajax, name='assign_ticket_user'),
    path('ticket/<str:ticket_id>/notify-n8n/', views.notify_ticket_n8n_ajax, name='notify_ticket_n8n'),
    path('cluster/<str:cluster_id>/create-ticket/', views.create_ticket_in_cluster_ajax, name='create_ticket_in_cluster'),
    path('cluster/<str:cluster_id>/vectorizar-ia/', views.vectorize_cluster_tickets_ajax, name='vectorizar_ia_cluster'),
    path('api/search-tickets-autocomplete/', views.search_tickets_autocomplete_ajax, name='search_tickets_autocomplete'),
    path('ticket/<str:ticket_id>/restriccion-acceso/', views.create_restriccion_acceso_ajax, name='create_restriccion_acceso_ajax'),
    path('restriccion-acceso/<int:pk>/pdf/', views.export_restriccion_acceso_pdf, name='export_restriccion_acceso_pdf'),
    path('api/webhook/correo-cierre-callback/', views.webhook_correo_cierre_callback, name='webhook_correo_cierre_callback'),
    path('app/ticket/<int:pk>/', views.mobile_ticket_detalle_view, name='mobile_ticket_detalle'),
    
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
    
    # Cronogramas Predefinidos (Templates)
    path('cronogramas-predefinidos/', views.cronograma_predefinido_lista_view, name='callcenter_cronogramas_lista'),
    path('cronogramas-predefinidos/nuevo/', views.cronograma_predefinido_edit_view, name='callcenter_cronograma_nuevo'),
    path('cronogramas-predefinidos/<int:pk>/', views.cronograma_predefinido_detalle_view, name='callcenter_cronograma_detalle'),
    path('cronogramas-predefinidos/<int:pk>/editar/', views.cronograma_predefinido_edit_view, name='callcenter_cronograma_editar'),
    path('api/cronograma-predefinido/<int:pk>/items/', views.api_get_cronograma_items_ajax, name='api_get_cronograma_items_ajax'),
    path('api/webhook/vector-update/', views.webhook_ticket_vector_callback, name='webhook_ticket_vector_callback'),
]

