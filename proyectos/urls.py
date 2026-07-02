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
]
