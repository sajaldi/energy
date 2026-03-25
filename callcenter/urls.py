from django.urls import path
from . import views

app_name = 'callcenter'

urlpatterns = [
    path('webhook-new-ticket/', views.webhook_new_ticket, name='webhook_new_ticket'),
    path('api/ticket/<str:folio>/pdf/', views.generate_ticket_pdf_view, name='generate_ticket_pdf'),
    path('api/ticket/<str:folio>/upload_evidencia/', views.webhook_evidencia_ticket, name='webhook_evidencia_ticket'),
    path('api/ticket/<int:ticket_id>/enviar-power-automate/', views.send_ticket_to_power_automate_view, name='send_power_automate'),
    path('buscar/', views.ticket_search_view, name='buscar_tickets'),
]
