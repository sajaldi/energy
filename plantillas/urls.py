from django.urls import path
from . import views

app_name = 'plantillas'

urlpatterns = [
    # Selector interactivo de modelo
    path('', views.selector_plantilla_view, name='selector'),

    # API: Listar todos los modelos disponibles
    path('api/modelos/', views.lista_modelos, name='api_modelos'),

    # API: Campos de un modelo específico
    path('api/campos/<int:content_type_id>/', views.campos_modelo_json, name='api_campos'),

    # Descargar plantilla en blanco para un modelo
    path('generar/<int:content_type_id>/', views.generar_plantilla_view, name='generar'),

    # Descargar plantilla poblada con datos reales de un registro
    path('exportar/<int:plantilla_id>/<str:app_label>/<str:model_name>/<int:registro_pk>/',
         views.poblar_plantilla_view, name='exportar'),
]
