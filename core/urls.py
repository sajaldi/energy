from django.urls import path
from . import views

# Esta línea es la que DEFINE el namespace 'core' para este conjunto de URLs.
app_name = 'core'

urlpatterns = [
    # Ruta para la página de inicio
    path('import-consumo/', views.import_excel, name='import_consumo'),
    path('reportes/consumo-mensual/', views.reporte_consumo_mensual, name='reporte_consumo_mensual'),
    # Ruta para la importación
   # Ruta para el detalle diario AJAX
    path('reportes/detalle-diario/<int:medidor_id>/<str:mes_str>/',views.reporte_consumo_diario,name='reporte_detalle_diario_ajax'
    ),
]
