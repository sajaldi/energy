from django.urls import path
from . import views

# Define el namespace para evitar colisiones de nombres
app_name = 'core'

urlpatterns = [
    # Ruta para la página de inicio
    path('import-consumo/', views.import_excel, name='import_consumo'),
    path('reportes/consumo-mensual/', views.reporte_consumo_mensual, name='reporte_consumo_mensual'),
    # Ruta para la importación
    path('reportes/detalle-diario/<int:medidor_id>/<str:mes_str>/', views.reporte_consumo_diario, name='reporte_detalle_diario_ajax'),
    path('finalizar-tutorial/', views.finalizar_tutorial, name='finalizar_tutorial'),
]
