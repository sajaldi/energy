from django.urls import path
from . import views

app_name = 'almacen'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard, name='dashboard'),
    
    # Gestión de solicitudes (Órdenes)
    path('solicitudes/', views.solicitudes_pendientes, name='solicitudes_pendientes'),
    path('ordenes/<int:orden_id>/', views.detalle_orden, name='detalle_orden'),
    path('ordenes/<int:orden_id>/despachar/', views.procesar_despacho, name='procesar_despacho'),
    
    # Gestión de materiales
    path('materiales/crear/', views.crear_material, name='crear_material'),
    path('materiales/asignar/', views.asignar_materiales, name='asignar_materiales'),
    path('materiales/pendientes/', views.materiales_pendientes, name='materiales_pendientes'),
    path('materiales/crear-desde-solicitud-ajax/', views.crear_material_desde_solicitud_ajax, name='crear_material_desde_solicitud_ajax'),
    path('materiales/verificar-duplicados-ajax/', views.verificar_materiales_duplicados_ajax, name='verificar_materiales_duplicados_ajax'),
    path('materiales/vincular-existente-ajax/', views.vincular_material_existente_ajax, name='vincular_material_existente_ajax'),

    # Almacenes e Inventario
    path('almacenes/', views.lista_almacenes, name='lista_almacenes'),
    path('almacenes/<int:ubicacion_id>/', views.detalle_almacen, name='detalle_almacen'),
]
