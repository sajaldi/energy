from django.urls import path
from . import views
from .views import mobile_crear_solicitud
from .api_materials import api_list_materials, api_list_categories, api_master_sync

app_name = 'inventarios'

urlpatterns = [
    path('', views.inventario_dashboard, name='dashboard'),
    path('crear-solicitud/', views.crear_solicitud_dashboard, name='crear_solicitud'),
    path('api/stock/<int:material_id>/', views.api_get_material_stock, name='api_get_material_stock'),
    path('api/material/<int:material_id>/update/', views.api_update_material_mobile, name='api_update_material_mobile'),
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
    path('catalogo/', views.master_catalog, name='master_catalog'),

    # Mobile Views
    path('mobile/dashboard/', views.mobile_inventario_dashboard, name='mobile_dashboard'),
    path('mobile/movimientos/', views.mobile_historial_movimientos, name='mobile_movimientos'),
    path('mobile/pedidos/', views.mobile_lista_pedidos, name='mobile_lista_pedidos'),
    path('mobile/pedidos/<int:pk>/', views.mobile_detalle_pedido, name='mobile_detalle_pedido'),
    path('mobile/crear-solicitud/', mobile_crear_solicitud, name='mobile_crear_solicitud'),
    path('mobile/catalog/', views.mobile_catalog, name='mobile_catalog'),
    path('mobile/gestion-salidas/', views.mobile_inventario_dashboard, name='mobile_gestion_salidas'),
    path('mobile/devolucion/', views.mobile_devolucion_view, name='mobile_devolucion'),
    path('mobile/devolucion/historial/', views.mobile_historial_devoluciones_view, name='mobile_historial_devoluciones'),
    path('api/devolucion/registrar/', views.api_registrar_devolucion, name='api_registrar_devolucion'),
    path('api/usuarios/search/', views.api_search_usuarios, name='api_search_usuarios'),
    path('api/ordenes-trabajo/search/', views.api_search_ordenes_trabajo, name='api_search_ot'),
    path('api/niveles/', views.api_niveles_por_edificio, name='api_niveles_edificio'),

    # Impresión de Etiquetas
    path('etiquetas/', views.imprimir_etiquetas_view, name='imprimir_etiquetas'),
    path('etiquetas/generar-pdf/', views.generar_pdf_etiquetas, name='generar_pdf_etiquetas'),
    path('api/print-label/<int:material_id>/', views.api_print_label, name='api_print_label'),
    path('api/ingreso-lote/', views.api_ingreso_lote, name='api_ingreso_lote'),
    path('api/solicitudes/search/', views.api_list_solicitudes, name='api_list_solicitudes'),
    path('api/solicitudes/<str:pk>/items/', views.api_get_solicitud_items, name='api_get_solicitud_items'),
    path('api/material/quick-create/', views.api_create_material, name='api_create_material'),
    path('api/pedidos-pendientes/', views.api_pedidos_pendientes_almacen, name='api_pedidos_pendientes_almacen'),
    path('api/pedidos/<int:pk>/detalle/', views.api_detalle_solicitud_almacen, name='api_detalle_solicitud_almacen'),
    path('api/pedidos/<int:pk>/despachar/', views.api_despachar_solicitud, name='api_despachar_solicitud'),
    path('api/discrepancy/resolve/', views.api_resolver_discrepancia, name='api_resolver_discrepancia'),
    path('api/sync-master/', api_master_sync, name='api_master_sync'),
    path('registrar-salida/', views.registrar_salida_view, name='registrar_salida'),
    path('manifest.json', views.pwa_manifest, name='pwa_manifest'),
    path('sw.js', views.pwa_sw, name='pwa_sw'),
]
