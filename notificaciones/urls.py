from django.urls import path
from . import views

app_name = 'notificaciones'

urlpatterns = [
    path('api/conteo/', views.api_conteo, name='api_conteo'),
    path('api/no-leidas/', views.api_no_leidas, name='api_no_leidas'),
    path('api/todas/', views.api_todas, name='api_todas'),
    path('api/marcar-leida/', views.api_marcar_leida, name='api_marcar_leida'),
    path('', views.pagina_notificaciones, name='pagina_admin'),
]
