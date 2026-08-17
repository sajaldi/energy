from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
    path('api/crear-actividad/', views.crear_actividad_api, name='crear_actividad_api'),
    path('api/actualizar-actividad/<int:actividad_id>/', views.actualizar_actividad_api, name='actualizar_actividad_api'),
    path('cronograma/<int:proyecto_id>/', views.cronograma_proyecto, name='cronograma'),
    path('gantt/<int:proyecto_id>/', views.gantt_proyecto, name='gantt_proyecto'),
    path('chatbot-asistente/', views.chatbot_asistente, name='chatbot_asistente'),
    path('repositorio-documentos/<int:proyecto_id>/', views.repositorio_documentos, name='repositorio_documentos'),
    path('dashboard/', views.dashboard_proyectos_fiori, name='dashboard'),
    path('nuevo/', views.crear_proyecto, name='crear'),
    path('proyecto/<int:pk>/', views.proyecto_detalle_fiori, name='detalle_fiori'),
    path('proyecto/<int:pk>/update/', views.update_proyecto_api, name='update_api'),
    path('proyecto/<int:pk>/actividades/bulk-update/', views.update_actividades_bulk_api, name='actividades_bulk_update'),
    path('proyecto/<int:pk>/actividades/<int:act_id>/delete/', views.delete_actividad_api, name='delete_actividad'),
    path('proyecto/<int:pk>/kanban/api/', views.kanban_actividades_api, name='kanban_actividades_api'),
    path('proyecto/<int:pk>/documentos/upload/', views.upload_documento_proyecto_api, name='upload_documento'),
    path('proyecto/<int:pk>/documentos/upload/', views.upload_documento_proyecto_api, name='upload_documento'),
    path('proyecto/<int:proyecto_pk>/link-ot/', views.link_ot_api, name='link_ot'),
    path('proyecto/<int:proyecto_pk>/link-requisicion/', views.link_requisicion_api, name='link_requisicion'),
    path('api/actividad/<int:actividad_id>/detalle/', views.activity_detail_api, name='activity_detail_api'),
    path('proyecto/<int:pk>/reporte/', views.reporte_proyecto, name='reporte'),
    path('proyecto/<int:pk>/reporte-observaciones/', views.reporte_observaciones, name='reporte_observaciones'),
    path('proyecto/<int:proyecto_pk>/observaciones/crear/', views.crear_observacion_api, name='crear_observacion'),
    path('proyecto/<int:proyecto_pk>/observaciones/<int:obs_id>/detalle/', views.detalle_observacion_api, name='detalle_observacion'),
    path('proyecto/<int:proyecto_pk>/observaciones/<int:obs_id>/actualizar/', views.actualizar_observacion_api, name='actualizar_observacion'),
    path('proyecto/<int:proyecto_pk>/observaciones/<int:obs_id>/eliminar/', views.eliminar_observacion_api, name='eliminar_observacion'),

    # Planos PDF
    path('proyecto/<int:pk>/planos/', views.listar_planos_api, name='listar_planos_api'),
    path('proyecto/<int:pk>/planos/upload/', views.upload_plano_api, name='upload_plano_api'),
    path('proyecto/<int:pk>/planos/<int:plano_id>/delete/', views.delete_plano_api, name='delete_plano_api'),
    path('proyecto/<int:pk>/planos/<int:plano_id>/download/', views.download_plano, name='download_plano'),
    path('proyecto/<int:pk>/planos/<int:plano_id>/visor/', views.visor_plano_proyecto, name='visor_plano_proyecto'),
    path('proyecto/<int:pk>/planos/<int:plano_id>/visor-mobile/', views.visor_plano_proyecto_mobile, name='visor_plano_proyecto_mobile'),

    # Pines de observación en planos
    path('proyecto/<int:pk>/planos/<int:plano_id>/pines/', views.listar_pines_plano_api, name='listar_pines_plano_api'),
    path('proyecto/<int:pk>/planos/<int:plano_id>/pines/crear/', views.crear_pin_plano_api, name='crear_pin_plano_api'),
    path('proyecto/<int:pk>/planos/<int:plano_id>/pines/<int:pin_id>/eliminar/', views.eliminar_pin_plano_api, name='eliminar_pin_plano_api'),
    path('proyecto/<int:pk>/planos/<int:plano_id>/pines/<int:pin_id>/mover/', views.mover_pin_plano_api, name='mover_pin_plano_api'),

    # Fotos de pines de observación
    path('proyecto/<int:pk>/planos/<int:plano_id>/pines/<int:pin_id>/fotos/subir/', views.subir_fotos_pin_api, name='subir_fotos_pin_api'),
    path('proyecto/<int:pk>/planos/<int:plano_id>/pines/<int:pin_id>/fotos/<int:foto_id>/eliminar/', views.eliminar_foto_pin_api, name='eliminar_foto_pin_api'),

    # Áreas de planos
    path('proyecto/<int:pk>/planos/<int:plano_id>/areas/crear/', views.crear_area_plano_api, name='crear_area_plano_api'),
    path('proyecto/<int:pk>/planos/<int:plano_id>/areas/<int:area_id>/editar/', views.editar_area_plano_api, name='editar_area_plano_api'),
    path('proyecto/<int:pk>/planos/<int:plano_id>/areas/<int:area_id>/eliminar/', views.eliminar_area_plano_api, name='eliminar_area_plano_api'),

    # Elementos del Proyecto
    path('proyecto/<int:pk>/elementos/', views.api_elementos_lista, name='api_elementos_lista'),
    path('proyecto/<int:pk>/elementos/crear/', views.api_elemento_crear, name='api_elemento_crear'),
    path('proyecto/<int:pk>/elementos/<int:elemento_id>/actualizar/', views.api_elemento_actualizar, name='api_elemento_actualizar'),
    path('proyecto/<int:pk>/elementos/<int:elemento_id>/eliminar/', views.api_elemento_eliminar, name='api_elemento_eliminar'),
    path('proyecto/<int:pk>/elementos/<int:elemento_id>/documentos/', views.api_elemento_documentos, name='api_elemento_documentos'),
    path('proyecto/<int:pk>/elementos/<int:elemento_id>/documentos/subir/', views.api_elemento_subir_documento, name='api_elemento_subir_documento'),
    path('proyecto/<int:pk>/elementos/<int:elemento_id>/documentos/<int:doc_id>/eliminar/', views.api_elemento_eliminar_documento, name='api_elemento_eliminar_documento'),

    # Comunicaciones del proyecto
    path('proyecto/<int:pk>/comunicados/crear/', views.crear_comunicado_proyecto_api, name='crear_comunicado_proyecto'),
]
