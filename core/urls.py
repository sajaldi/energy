from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Landing page en la raíz
    path('', views.landing_page, name='landing_page'),
    # Ruta para la página de inicio
    path('import-consumo/', views.import_excel, name='import_consumo'),
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
    path('vistas/guardar/', views.guardar_vista_personalizada, name='guardar_vista'),
    path('vistas/eliminar/<int:vista_id>/', views.eliminar_vista_personalizada, name='eliminar_vista'),
]
