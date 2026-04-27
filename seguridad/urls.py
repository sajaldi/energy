from django.urls import path
from . import views

app_name = 'seguridad'

urlpatterns = [
    path('permiso/generar/ot/<int:ot_id>/', views.generar_permiso_de_ot, name='generar_permiso_ot'),
    path('permiso/<int:permiso_id>/', views.detalle_permiso_view, name='detalle_permiso'),
    
    # Mobile views
    path('app/permisos/', views.mobile_mis_permisos, name='mobile_mis_permisos'),
    path('app/permiso/<int:pk>/', views.mobile_permiso_detalle, name='mobile_permiso_detalle'),
    path('app/permiso/generar/<int:ot_id>/', views.mobile_generar_permiso, name='mobile_generar_permiso'),
    path('app/permiso/pdf/<int:permiso_id>/', views.generar_permiso_pdf_view, name='mobile_permiso_pdf'),

    # Confiscaciones
    path('app/confiscaciones/', views.mobile_confiscaciones_lista, name='mobile_confiscaciones_lista'),
    path('app/confiscaciones/nueva/', views.mobile_confiscacion_nueva, name='mobile_confiscacion_nueva'),
    path('app/confiscaciones/<int:pk>/', views.mobile_confiscacion_ejecutar, name='mobile_confiscacion_ejecutar'),
    path('app/confiscaciones/<int:pk>/agregar/', views.mobile_confiscacion_agregar_objeto, name='mobile_confiscacion_agregar_objeto'),
    path('app/confiscaciones/objeto/<int:pk>/editar/', views.mobile_confiscacion_editar_objeto, name='mobile_confiscacion_editar_objeto'),
    path('app/confiscaciones/objeto/status/<int:pk>/', views.mobile_confiscacion_objeto_actualizar, name='mobile_confiscacion_objeto_actualizar'),
    path('app/confiscaciones/pdf/<int:pk>/', views.mobile_confiscacion_pdf_view, name='mobile_confiscacion_pdf'),
    path('app/confiscaciones/confirmar-carga/<int:pk>/', views.mobile_confiscacion_confirmar_carga, name='mobile_confiscacion_confirmar_carga'),
    path('app/confiscaciones/api/confirmar-carga-objeto/', views.api_confirmar_carga_objeto, name='api_confirmar_carga_objeto'),
    
    # Almacenes
    path('app/almacen/recepcion/', views.mobile_almacen_recepcion, name='mobile_almacen_recepcion'),
    path('app/almacen/validar-lote/<int:pk>/', views.mobile_almacen_validar_lote, name='mobile_almacen_validar_lote'),
    path('app/almacen/api/almacenar-objeto/', views.api_almacen_almacenar_objeto, name='api_almacen_almacenar_objeto'),

    # Entrega / Salida
    path('app/almacen/entrega/validar/', views.mobile_almacen_entrega_validar, name='mobile_almacen_entrega_validar'),
    path('app/almacen/api/confirmar-entrega/', views.api_almacen_confirmar_entrega, name='api_almacen_confirmar_entrega'),
    path('app/almacen/entrega/pdf/<int:pk>/', views.mobile_confiscacion_entrega_pdf_view, name='mobile_confiscacion_entrega_pdf'),
    path('app/confiscacion/imprimir/<int:pk>/', views.mobile_confiscacion_imprimir_etiqueta, name='mobile_confiscacion_imprimir_etiqueta'),
    path('app/perfil/', views.mobile_perfil, name='mobile_perfil'),

    # Dashboards de Gestión
    path('gestion/tipos-permisos/', views.tipo_permiso_dashboard, name='tipo_permiso_dashboard'),
    path('api/tipo-permiso/<int:pk>/', views.tipo_permiso_detail_api, name='tipo_permiso_detail_api'),
    path('api/tipo-permiso/save/', views.tipo_permiso_save_api, name='tipo_permiso_save_api'),
    path('api/tipo-permiso/requisitos/save/', views.tipo_permiso_requisitos_save_api, name='tipo_permiso_requisitos_save_api'),
]
