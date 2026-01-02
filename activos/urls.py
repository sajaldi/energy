from django.urls import path
from . import views

app_name = 'activos'

from . import views_sync

urlpatterns = [
    path('visor/<int:visor_id>/', views.visor_plano, name='visor_plano'),
    path('api/guardar-pin/', views.guardar_pin, name='guardar_pin'),
    path('api/eliminar-pin/<int:pin_id>/', views.eliminar_pin, name='eliminar_pin'),
    path('api/import-progress/<str:task_id>/', views.import_progress, name='import_progress'),
    path('api/get-import-progress/', views.get_import_progress, name='get_realtime_progress'),
    
    # Sincronización masiva
    path('api/submit-all/', views_sync.submit_all_activos, name='submit_all_activos'),
    
    # Arbol Interactivo
    path('arbol-ubicaciones/', views.arbol_activos_view, name='arbol_activos'),
    path('api/ubicaciones-root/', views.api_ubicaciones_root, name='api_ubicaciones_root'),
    path('api/ubicaciones-children/<int:parent_id>/', views.api_ubicaciones_children, name='api_ubicaciones_children'),
    path('api/ubicacion-detalle/<int:ubicacion_id>/', views.api_ubicacion_detalle, name='api_ubicacion_detalle'),
    path('api/activo-detalle/<int:activo_id>/', views.api_activo_detalle, name='api_activo_detalle'),
]
