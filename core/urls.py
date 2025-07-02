from django.urls import path
from . import views

# Define el namespace para evitar colisiones de nombres
app_name = 'core'

urlpatterns = [
    # URL para la página de importación
    path('import-excel/', views.import_excel, name='import_excel'),
    
    # URL para el menú de administración personalizado (si lo usas)
    path('admin-menu/', views.admin_menu, name='admin_menu'),

    # URL para el generador de reportes principal
    path('reporte-consumo/', views.reporte_consumo_mensual, name='reporte_consumo_mensual'),
    
    # URL para el detalle diario del reporte
    path('reporte-diario/<int:medidor_id>/<str:mes_str>/', views.reporte_consumo_diario, name='reporte_consumo_diario'),
    
    # NUEVO: Una vista para la página de inicio (raíz)
    # Apuntará a una vista simple o, si prefieres, al menú de administración.
    path('', views.admin_menu, name='inicio'), # O crea una nueva vista 'inicio_view'
]