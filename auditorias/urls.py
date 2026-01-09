from django.urls import path
from . import views

app_name = 'auditorias'

urlpatterns = [
    path('', views.lista_auditorias, name='lista_auditorias'),
    path('api/inicializar/<int:auditoria_id>/', views.api_inicializar_auditoria, name='api_inicializar'),
    path('api/procesar-escaneo/<int:auditoria_id>/', views.api_procesar_escaneo, name='api_procesar_escaneo'),
    path('ejecutar/<int:auditoria_id>/', views.ejecutar_auditoria, name='ejecutar'),
    path('api/finalizar/<int:auditoria_id>/', views.api_finalizar_auditoria, name='api_finalizar'),
]
