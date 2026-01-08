from django.urls import path
from . import views

app_name = 'presupuestos'

urlpatterns = [
    path('cronograma/', views.cronograma_presupuesto, name='cronograma'),
    path('cronograma/<int:pk>/', views.cronograma_presupuesto, name='cronograma_detalle'),
    path('cronograma/grupo/<int:pk>/', views.cronograma_grupal, name='cronograma_grupal'),
    path('api/update_monto/', views.api_update_monto_mensual, name='api_update_monto'),
    path('api/update_monto/', views.api_update_monto_mensual, name='api_update_monto'),
    path('api/create_item/', views.api_create_item, name='api_create_item'),
    path('api/create_partida/', views.api_create_partida, name='api_create_partida'),
    path('api/delete_item/', views.api_delete_item, name='api_delete_item'),
    path('api/delete_partida/', views.api_delete_partida, name='api_delete_partida'),
    path('exportar_excel/<int:pk>/', views.exportar_cronograma_excel, name='exportar_excel'),
    path('exportar_pdf/<int:pk>/', views.exportar_cronograma_pdf, name='exportar_pdf'),
    path('exportar_grupo_pdf/<int:pk>/', views.exportar_cronograma_grupal_pdf, name='exportar_cronograma_grupal_pdf'),
]
