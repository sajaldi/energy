from django.urls import path
from . import views, views_wizard

app_name = 'auditorias'

urlpatterns = [
    path('', views.lista_auditorias, name='lista_auditorias'),
    path('nuevo/', views_wizard.auditoria_wizard, name='wizard_auditoria'),
    path('api/inicializar/<int:auditoria_id>/', views.api_inicializar_auditoria, name='api_inicializar'),
    path('api/procesar-escaneo/<int:auditoria_id>/', views.api_procesar_escaneo, name='api_procesar_escaneo'),
    path('api/actualizar-conteo/<int:auditoria_id>/', views.api_actualizar_conteo, name='api_actualizar_conteo'),
    path('ejecutar/<int:auditoria_id>/', views.ejecutar_auditoria, name='ejecutar'),
    path('api/finalizar/<int:auditoria_id>/', views.api_finalizar_auditoria, name='api_finalizar'),
]
