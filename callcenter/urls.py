from django.urls import path
from . import views

app_name = 'callcenter'

urlpatterns = [
    path('webhook-new-ticket/', views.webhook_new_ticket, name='webhook_new_ticket'),
    path('api/ticket/<str:folio>/pdf/', views.generate_ticket_pdf_view, name='generate_ticket_pdf'),
]
