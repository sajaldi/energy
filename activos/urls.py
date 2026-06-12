from django.urls import path
from . import views

app_name = 'activos'

from . import views_sync
from . import views_rutinas
from . import views_celery
from . import views_categorias
from . import views_modelos

urlpatterns = [
    # Dashboard de Categorías
    path('categorias/dashboard/', views_categorias.categorias_dashboard, name='categorias_dashboard'),
    path('api/categoria-detalle/<int:pk>/', views_categorias.categoria_detail_api, name='categoria_detail_api'),
    path('api/categoria-save/', views_categorias.categoria_save_api, name='categoria_save_api'),
    path('api/categoria-delete/<int:pk>/', views_categorias.categoria_delete_api, name='categoria_delete_api'),
    path('api/categoria-move/<int:pk>/', views_categorias.categoria_move_api, name='categoria_move_api'),
    path('api/categoria-modelos/<int:pk>/', views_categorias.get_categoria_modelos_api, name='get_categoria_modelos_api'),
    path('api/modelo-detalle-completo/<int:pk>/', views_categorias.get_modelo_details_api, name='get_modelo_details_api'),

    # Dashboard de Modelos
    path('modelos/dashboard/', views_modelos.modelos_dashboard, name='modelos_dashboard'),
    path('api/modelo-fiori-save/', views_modelos.modelo_save_api, name='modelo_fiori_save'),
    path('api/modelo-fiori-delete/<int:pk>/', views_modelos.modelo_delete_api, name='modelo_fiori_delete'),
    path('api/modelo-fiori-get/', views_modelos.modelo_detail_api, name='modelo_fiori_get'),
    path('api/categoria-caracteristicas/', views_modelos.categoria_caracteristicas_api, name='categoria_caracteristicas_api'),

    path('visor/<int:visor_id>/', views.visor_plano, name='visor_plano'),
    path('visor/plano/<int:plano_id>/', views.visor_plano, name='visor_plano_por_plano'),
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
    path('api/ubicacion-categoria-activos/<int:ubicacion_id>/<str:categoria_id>/', views.api_ubicacion_categoria_activos, name='api_ubicacion_categoria_activos'),
    path('api/activo-detalle/<int:activo_id>/', views.api_activo_detalle, name='api_activo_detalle'),
    path('api/explorer-search/', views.api_explorer_search, name='api_explorer_search'),
    path('app/activo/<int:pk>/', views.mobile_activo_detalle, name='mobile_activo_detalle'),
    path('app/buscar/', views.mobile_busqueda_activos, name='mobile_busqueda'),
    path('api/buscar-activos-json/', views.api_buscar_activos_json, name='api_buscar_activos_json'),
    path('api/buscar-modelos-json/', views.api_buscar_modelos_json, name='api_buscar_modelos_json'),
    path('api/get_rutinas_ubicacion/', views_rutinas.get_rutinas_ubicacion, name='get_rutinas_ubicacion'),
    path('app/ubicaciones/', views.mobile_ubicaciones, name='mobile_ubicaciones'),
    path('app/ubicaciones/<int:parent_id>/', views.mobile_ubicaciones, name='mobile_ubicaciones_child'),
    path('api/modelo-detalle/<int:modelo_id>/', views.api_modelo_detalle, name='api_modelo_detalle'),
    
    # Administrador / Scanner de Ubicaciones Físicas (Móvil)
    path('app/admin/', views.mobile_admin_dashboard, name='mobile_admin_dashboard'),
    path('app/admin/scanner/', views.mobile_admin_ubicaciones_scanner, name='mobile_admin_ubicaciones_scanner'),
    path('api/admin/scanner/handler/', views.mobile_admin_ubicaciones_handler, name='mobile_admin_ubicaciones_handler'),
    path('app/admin/ubicacion/asignar/', views.mobile_admin_ubicacion_asignar, name='mobile_admin_ubicacion_asignar'),

    # QR Label Generator and WYSIWYG
    path('etiquetas/designer/<int:plantilla_id>/', views.qr_designer_view, name='qr_designer_view'),
    path('etiquetas/designer/save/<int:plantilla_id>/', views.qr_designer_save, name='qr_designer_save'),
    path('etiquetas/generador/', views.qr_generator_dashboard, name='qr_generator_dashboard'),
    path('etiquetas/generador/pdf/', views.qr_generator_pdf, name='qr_generator_pdf'),

    
    # Celery Industrial Import
    path('celery-import/', views_celery.import_activos_view, name='celery_import_activos'),
    path('celery-import/process/', views_celery.import_activos_process, name='celery_import_process'),
    path('celery-import/progress/', views_celery.import_activos_progress, name='celery_import_progress'),
    path('celery-cancel-task/<str:task_id>/', views_celery.celery_cancel_task, name='celery_cancel_task'),
    path('celery-download-template/', views_celery.download_activos_template, name='celery_download_template'),
    path('import-dashboard/', views_celery.imports_dashboard, name='imports_dashboard'),

    # Super Filtro de Activos
    path('celery-import/filter-options/', views_celery.superfilter_options, name='superfilter_options'),
    path('celery-import/filter/', views_celery.superfilter_query, name='superfilter_query'),
    path('celery-import/filter/export/', views_celery.superfilter_export, name='superfilter_export'),
    path('celery-import/vistas/', views_celery.superfilter_vistas, name='superfilter_vistas'),
    path('filter/reportes/', views_celery.superfilter_reportes, name='sf-reportes'),
    path('filter/reportes/cancelar/', views_celery.superfilter_reportes_cancelar, name='sf-reportes-cancelar'),


    # Celery Bienes Afectos Import
    path('celery-import-bienes/', views_celery.import_bienes_afectos_view, name='celery_import_bienes'),
    path('celery-import-bienes/process/', views_celery.import_bienes_afectos_process, name='celery_import_bienes_process'),
    path('celery-import-bienes/progress/', views_celery.import_bienes_afectos_progress, name='celery_import_bienes_progress'),
    path('celery-download-template-bienes/', views_celery.download_bienes_template, name='celery_download_template_bienes'),
    
    # Edición personalizada de activos
    path('editar-activo/<int:pk>/', views.activo_edit_view, name='activo_edit'),

    # Celery Categorías Import
    path('celery-import-categorias/', views_celery.import_categorias_view, name='celery_import_categorias'),
    path('celery-import-categorias/process/', views_celery.import_categorias_process, name='celery_import_categorias_process'),
    path('celery-import-categorias/progress/', views_celery.import_categorias_progress, name='celery_import_categorias_progress'),
    path('celery-download-template-categorias/', views_celery.download_categorias_template, name='celery_download_template_categorias'),

    # Documentos de Alta/Baja
    # Documentos de Alta/Baja
    path('documento-altabaja/<int:pk>/imprimir/', views.print_altabaja, name='print_altabaja'),
    path('plano-proxy/<int:plano_id>/', views.plano_documento_proxy, name='plano_documento_proxy'),
    
    # PDF de QR Punto Medicion
    path('punto-medicion/<int:pk>/qr/', views_rutinas.punto_medicion_qr_pdf, name='punto_medicion_qr_pdf'),

    # Fiori Dashboard y Explorador
    path('activo/<int:pk>/fiori/', views.activo_fiori_view, name='activo_fiori'),
    path('fiori-explorer/', views.fiori_explorer_view, name='fiori_explorer'),
    path('fiori-explorer/<int:ubicacion_id>/', views.fiori_explorer_view, name='fiori_explorer_at'),
    
    # Fotos de Ubicación
    path('api/ubicacion/upload-fotos/', views.api_upload_foto_ubicacion, name='api_upload_foto_ubicacion'),

    # Gestor de Ubicaciones (Mobile APP Style)
    path('ubicaciones/gestor/', views.ubicacion_manager_view, name='ubicacion_manager'),
    path('api/ubicaciones/list/', views.api_ubicacion_list, name='api_ubicacion_list'),
    path('api/ubicaciones/save/', views.api_ubicacion_save, name='api_ubicacion_save'),
    path('api/ubicaciones/delete/<int:ubicacion_id>/', views.api_ubicacion_delete, name='api_ubicacion_delete'),
]
