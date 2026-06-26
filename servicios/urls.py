from django.urls import path
from . import views

app_name = 'servicios'

urlpatterns = [
    path('kpi/', views.kpi_form_view, name='kpi_form'),
    path('kpi/<int:pk>/', views.kpi_form_view, name='kpi_form_edit'),
    # Auditorías
    path('auditoria/', views.auditoria_form_view, name='auditoria_form'),
    path('auditoria/<int:pk>/', views.auditoria_form_view, name='auditoria_form_edit'),
    # Import endpoints (existing)
    path('kpi/import-background/', views.import_kpis_background, name='kpi_import_background'),
    path('kpi/import-background/process/', views.import_kpis_process, name='kpi_import_process'),
    path('kpi/import-background/progress/', views.import_kpis_progress, name='kpi_import_progress'),
    path('kpi/dashboard/', views.kpi_dashboard_view, name='kpi_dashboard'),
    # RAG + Búsqueda Vectorial Semántica
    path('kpi/buscar/', views.kpi_buscador_view, name='kpi_buscador'),
    path('kpi/api/busqueda-semantica/', views.api_kpi_busqueda_semantica, name='api_kpi_busqueda'),
    path('kpi/api/rag/', views.api_kpi_rag, name='api_kpi_rag'),
    path('kpi/api/vectorize-all/', views.api_kpi_vectorize_all, name='api_kpi_vectorize_all'),
    # Documentos directos del KPI
    path('kpi/<int:pk>/subir-archivo/', views.api_kpi_subir_archivo, name='api_kpi_subir_archivo'),
    path('kpi/archivo/<int:pk>/eliminar/', views.api_kpi_eliminar_archivo, name='api_kpi_eliminar_archivo'),
]
