from django.urls import path
from . import views

app_name = 'activos'

from . import views_sync
from . import views_rutinas

urlpatterns = [
    path('visor/<int:visor_id>/', views.visor_plano, name='visor_plano'),
    path('api/guardar-pin/', views.guardar_pin, name='guardar_pin'),
    path('api/eliminar-pin/<int:pin_id>/', views.eliminar_pin, name='eliminar_pin'),
    path('api/import-progress/<str:task_id>/', views.import_progress, name='import_progress'),
    path('api/get-import-progress/', views.get_import_progress, name='get_realtime_progress'),
    
    # Sincronización masiva
    path('api/submit-all/', views_sync.submit_all_activos, name='submit_all_activos'),
    
    # Arbol Interactivo
    path('explorador-jerarquico/', views.explorer_jerarquia_admin, name='explorador_jerarquico'),
    path('api/explorer-level/', views.api_get_explorer_level, name='api_explorer_level'),
    path('api/item-form/<str:item_type>/<int:item_id>/', views.api_item_form, name='api_item_form'),
    path('arbol-ubicaciones/', views.arbol_activos_view, name='arbol_activos'),
    path('api/ubicaciones-root/', views.api_ubicaciones_root, name='api_ubicaciones_root'),
    path('api/ubicaciones-children/<int:parent_id>/', views.api_ubicaciones_children, name='api_ubicaciones_children'),
    path('api/ubicacion-detalle/<int:ubicacion_id>/', views.api_ubicacion_detalle, name='api_ubicacion_detalle'),
    path('api/activo-detalle/<int:activo_id>/', views.api_activo_detalle, name='api_activo_detalle'),
    path('api/explorer-search/', views.api_explorer_search, name='api_explorer_search'),
    path('app/activo/<int:pk>/', views.mobile_activo_detalle, name='mobile_activo_detalle'),
    path('app/buscar/', views.mobile_busqueda_activos, name='mobile_busqueda'),
    path('api/buscar-activos-json/', views.api_buscar_activos_json, name='api_buscar_activos_json'),
    path('api/get_rutinas_ubicacion/', views_rutinas.get_rutinas_ubicacion, name='get_rutinas_ubicacion'),
    path('app/ubicaciones/', views.mobile_ubicaciones, name='mobile_ubicaciones'),
    path('app/ubicaciones/<int:parent_id>/', views.mobile_ubicaciones, name='mobile_ubicaciones_child'),
]
