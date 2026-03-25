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
]
