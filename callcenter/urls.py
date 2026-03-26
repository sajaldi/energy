from django.urls import path
from . import views

app_name = 'callcenter'

urlpatterns = [
    path('webhook-new-ticket/', views.webhook_new_ticket, name='webhook_new_ticket'),
    path('api/ticket/<str:folio>/pdf/', views.generate_ticket_pdf_view, name='generate_ticket_pdf'),
    path('api/ticket/<str:folio>/upload_evidencia/', views.webhook_evidencia_ticket, name='webhook_evidencia_ticket'),
    path('ticket/<int:ticket_id>/enviar-power-automate/', views.send_ticket_to_power_automate_view, name='send_power_automate'),
    path('buscar/', views.ticket_search_view, name='buscar_tickets'),
    
    # Visual Closure Interface
    path('dashboard/', views.ticket_dashboard_view, name='ticket_dashboard'),
    path('dashboard/cluster/<int:cluster_id>/', views.cluster_tickets_view, name='cluster_tickets'),
    path('ticket/<int:ticket_id>/cierre-visual/', views.ticket_cierre_visual_view, name='ticket_cierre_visual'),
    path('ticket/<int:ticket_id>/upload-evidencia/', views.upload_evidencia_ajax, name='upload_evidencia_visual'),
    path('ticket/<int:ticket_id>/delete-evidencia/<int:evidencia_id>/', views.delete_evidencia_ajax, name='delete_evidencia_visual'),
    path('update-descripcion-evidencia/<int:evidence_id>/', views.update_evidencia_descripcion_ajax, name='update_evidencia_descripcion_ajax'),
    path('search-activos/', views.search_activos_ajax, name='search_activos_ajax'),
    path('ticket/<int:ticket_id>/update-activo/', views.update_ticket_activo_ajax, name='update_ticket_activo_ajax'),
    path('get-assignable-users/', views.get_assignable_users_ajax, name='get_assignable_users'),
    path('ticket/<int:ticket_id>/assign-user/', views.assign_ticket_user_ajax, name='assign_ticket_user'),
    path('ticket/<int:ticket_id>/notify-n8n/', views.notify_ticket_n8n_ajax, name='notify_ticket_n8n'),
]
