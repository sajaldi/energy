from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    path('', views.lista_cursos, name='lista'),
    path('admin/upload-image/', views.upload_image, name='upload_image'),
    path('admin/<int:pk>/upload-image/', views.upload_image, name='upload_image_curso'),
    path('admin/<int:curso_id>/seccion/<int:seccion_id>/pagina/', views.gestionar_pagina, name='paginas_list'),
    path('admin/<int:curso_id>/seccion/<int:seccion_id>/pagina/<int:pagina_id>/', views.gestionar_pagina, name='pagina_editar'),
    path('admin/', views.lista_admin, name='lista_admin'),
    path('admin/nuevo/', views.editar_curso, name='crear_curso'),
    path('admin/<int:pk>/', views.editar_curso, name='editar_curso'),
    path('admin/<int:pk>/vista-previa/', views.visualizar_curso, name='visualizar'),
    path('admin/<int:pk>/asignar/', views.asignar_curso, name='asignar_curso'),
    path('admin/<int:pk>/asignar/<int:asignacion_id>/eliminar/', views.desasignar_curso, name='desasignar_curso'),
    path('admin/<int:pk>/estadisticas/', views.estadisticas_curso, name='estadisticas'),
    path('admin/<int:pk>/importar-scorm/', views.importar_scorm, name='importar_scorm'),
    path('admin/<int:pk>/scorm/<path:subpath>', views.servir_scorm, name='servir_scorm'),
    # Hotspot editor
    path('admin/imagen-interactiva/crear/', views.crear_imagen_interactiva, name='crear_imagen_interactiva'),
    path('admin/imagen-interactiva/<int:img_id>/', views.editar_imagen_interactiva, name='editar_imagen_interactiva'),
    path('admin/imagen-interactiva/<int:img_id>/hotspots/', views.api_hotspots, name='api_hotspots'),
    path('admin/imagen-interactiva/<int:img_id>/eliminar/', views.eliminar_imagen_interactiva, name='eliminar_imagen_interactiva'),
    # Acordeones
    path('admin/acordeon/guardar/', views.guardar_acordeones, name='guardar_acordeones'),
    # Carruseles
    path('admin/carrusel/guardar/', views.guardar_carrusel, name='guardar_carrusel'),
    path('admin/<int:pk>/libro-pdf/', views.libro_pdf, name='libro_pdf'),
    path('<int:pk>/', views.detalle_curso, name='detalle'),
    path('<int:pk>/certificado/', views.certificado_curso, name='certificado'),
    path('<int:pk>/heartbeat/', views.heartbeat_curso, name='heartbeat'),
    path('<int:pk>/seccion/<int:seccion_id>/completar/', views.marcar_completada, name='marcar_completada'),
]
