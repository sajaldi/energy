from django.urls import path
from . import views

app_name = 'comunicaciones'

urlpatterns = [
    path('api/create-transmittal/', views.api_create_transmittal, name='api_create_transmittal'),
    
    # Vistas HTML
    path('transmittals/', views.lista_transmittals, name='lista_transmittals'),
    path('transmittals/<int:comunicado_id>/', views.detalle_transmittal, name='detalle_transmittal'),
]
