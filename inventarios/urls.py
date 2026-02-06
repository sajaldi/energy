from django.urls import path
from . import views
from .api_materials import api_list_materials, api_list_categories

app_name = 'inventarios'

urlpatterns = [
    path('crear-solicitud/', views.crear_solicitud_dashboard, name='crear_solicitud'),
    path('api/stock/<int:material_id>/', views.api_get_material_stock, name='api_get_material_stock'),
    path('cart/add/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:material_id>/', views.cart_remove, name='cart_remove'),
    path('cart/detail/', views.cart_detail_view, name='cart_detail'),
    path('cart/checkout/', views.cart_checkout, name='cart_checkout'),
    path('escanear/', views.scanner_view, name='scanner'),
    path('api/sku/', views.api_get_material_by_sku, name='api_get_material_by_sku'),
    path('api/movimiento-rapido/', views.api_registrar_movimiento_rapido, name='api_registrar_movimiento_rapido'),
    
    # API para selector visual
    path('api/materials/', api_list_materials, name='api_list_materials'),
    path('api/categories/', api_list_categories, name='api_list_categories'),

    # Mobile Views
    path('mobile/pedidos/', views.mobile_lista_pedidos, name='mobile_lista_pedidos'),
    path('mobile/pedidos/<int:pk>/', views.mobile_detalle_pedido, name='mobile_detalle_pedido'),
]
