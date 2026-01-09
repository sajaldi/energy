from django.urls import path
from . import views

urlpatterns = [
    path('registrar-salida/', views.registrar_salida_view, name='registrar_salida'),
    path('api/stock/<int:material_id>/', views.api_get_material_stock, name='api_get_material_stock'),
    path('cart/add/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:material_id>/', views.cart_remove, name='cart_remove'),
    path('cart/detail/', views.cart_detail_view, name='cart_detail'),
    path('cart/checkout/', views.cart_checkout, name='cart_checkout'),
    path('escanear/', views.scanner_view, name='scanner'),
    path('api/sku/', views.api_get_material_by_sku, name='api_get_material_by_sku'),
    path('api/movimiento-rapido/', views.api_registrar_movimiento_rapido, name='api_registrar_movimiento_rapido'),
]
