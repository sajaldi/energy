from django.urls import path
from . import views
from . import views_energia
from .views_home import home, guardar_home_config
from .views_coolify import coolify_dashboard, coolify_redeploy, coolify_logs, coolify_stream_logs, coolify_build_logs, celery_logs, celery_stream_logs
from .views_impersonate import impersonate_start, impersonate_stop

app_name = 'core'

urlpatterns = [
    # Landing page en la raíz
    path('', views.landing_page, name='landing_page'),
    # Ruta para la página de inicio
    path('import-consumo/', views.import_excel, name='import_consumo'),
    path('import-consumo-async/', views.import_consumo_view, name='import_consumo_async'),
    path('import-status/<str:task_id>/', views.get_import_status, name='import_status'),
    path('reportes/consumo-mensual/', views.reporte_consumo_mensual, name='reporte_consumo_mensual'),
    path('reportes/consumo-interactivo/', views.reporte_consumos_interactivo, name='reporte_consumo_interactivo'),
    # Ruta para la importación
    path('reportes/detalle-diario/<int:medidor_id>/<str:mes_str>/', views.reporte_consumo_diario, name='reporte_detalle_diario_ajax'),
    path('finalizar-tutorial/', views.finalizar_tutorial, name='finalizar_tutorial'),
    path('app/', views.mobile_dashboard, name='mobile_dashboard'),
    path('app/scanner/', views.mobile_scanner, name='mobile_scanner'),
    path('app/qr/', views.qr_resolver, name='qr_resolver'),
    path('admin/global-search/', views.global_search, name='global_search'),
    path('portal/', views.system_portal, name='system_portal'),
    path('inicio/', home, name='home'),
    path('inicio/guardar/', guardar_home_config, name='guardar_home_config'),
    path('vistas/guardar/', views.guardar_vista_personalizada, name='guardar_vista'),
    path('vistas/eliminar/<int:vista_id>/', views.eliminar_vista_personalizada, name='eliminar_vista'),
    
    # Coolify Admin Dashboard
    path('devops/coolify/', coolify_dashboard, name='coolify_dashboard'),
    path('devops/coolify/redeploy/', coolify_redeploy, name='coolify_redeploy'),
    path('devops/coolify/logs/', coolify_logs, name='coolify_logs'),
    path('devops/coolify/logs/stream/', coolify_stream_logs, name='coolify_stream_logs'),
    path('devops/coolify/logs/build/', coolify_build_logs, name='coolify_build_logs'),
    path('devops/git-history/', views.git_history_view, name='git_history'),
    
    # Celery Live Logs
    path('devops/celery/logs/', celery_logs, name='celery_logs'),
    path('devops/celery/logs/stream/', celery_stream_logs, name='celery_stream_logs'),

    # Impersonation (solo superusuarios)
    path('impersonate/<int:user_id>/', impersonate_start, name='impersonate_start'),
    path('impersonate/stop/', impersonate_stop, name='impersonate_stop'),

    # Dashboard Energetico
    path('dashboard-energia/', views_energia.dashboard_energia, name='dashboard_energia'),
    
    # Dashboard TV Medidores
    path('medidores/dashboard-tv/', views_energia.medidores_tv_dashboard, name='medidores_tv_dashboard'),
    path('medidores/dashboard-tv/api/', views_energia.medidores_tv_api, name='medidores_tv_api'),
    path('medidores/dashboard-config/', views_energia.medidores_dashboard_config, name='medidores_dashboard_config'),
]
