"""
URL patterns para el módulo de Análisis de Riesgos de Negocio.
Incluido desde servicios/urls.py bajo el prefijo 'riesgos/'.
"""
from django.urls import path
from django.views.generic import RedirectView
from . import views_riesgos

urlpatterns = [
    # Raíz redirige al panel
    path('', RedirectView.as_view(url='panel/', permanent=False), name='riesgos_index'),

    # Panel de Riesgos (Dashboard)
    path('panel/', views_riesgos.panel_riesgos_view, name='panel'),

    # Mapa de Calor
    path('mapa-calor/', views_riesgos.mapa_calor_consolidado_view, name='mapa_calor_consolidado'),
    path('mapa-calor/<int:servicio_id>/', views_riesgos.mapa_calor_view, name='mapa_calor'),

    # Historial y Timeline
    path('<int:riesgo_id>/historial/', views_riesgos.historial_riesgo_view, name='historial'),

    # Exportaciones
    path('export/excel/', views_riesgos.export_riesgos_excel_view, name='export_excel'),
    path('export/pdf/<int:servicio_id>/', views_riesgos.export_matriz_pdf_view, name='export_pdf'),

    # API para wizard modal
    path('api/crear/', views_riesgos.api_crear_riesgo, name='api_crear_riesgo'),
]
