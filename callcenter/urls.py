from django.urls import path
from . import views

app_name = 'callcenter'

urlpatterns = [
    path('webhook-new-ticket/', views.webhook_new_ticket, name='webhook_new_ticket'),
    path('api/ticket/<str:folio>/pdf/', views.generate_ticket_pdf_view, name='generate_ticket_pdf'),
    path('api/ticket/<str:folio>/upload_evidencia/', views.webhook_evidencia_ticket, name='webhook_evidencia_ticket'),
    path('api/ticket/<int:ticket_id>/enviar-power-automate/', views.send_ticket_to_power_automate_view, name='send_power_automate'),
    path('buscar/', views.ticket_search_view, name='buscar_tickets'),
    
    # SAP Fiori Closure Interface
    path('dashboard/', views.ticket_dashboard_view, name='ticket_dashboard'),
    path('ticket/<int:ticket_id>/cierre-fiori/', views.ticket_cierre_fiori_view, name='ticket_cierre_fiori'),
    path('ticket/<int:ticket_id>/upload-evidencia/', views.upload_evidencia_ajax, name='upload_evidencia_fiori'),
    path('ticket/<int:ticket_id>/delete-evidencia/<int:evidencia_id>/', views.delete_evidencia_ajax, name='delete_evidencia_fiori'),
]
