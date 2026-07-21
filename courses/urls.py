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
    # API contenido de sección/página (para viewer interactivo)
    path('<int:pk>/api/contenido/<int:seccion_id>/', views.api_contenido_seccion, name='api_contenido_seccion'),
    path('<int:pk>/api/contenido/<int:seccion_id>/pagina/<int:pagina_id>/', views.api_contenido_pagina, name='api_contenido_pagina'),
    path('admin/<int:pk>/libro-pdf/', views.libro_pdf, name='libro_pdf'),
    path('<int:pk>/', views.detalle_curso, name='detalle'),
    path('<int:pk>/certificado/', views.certificado_curso, name='certificado'),
    path('<int:pk>/heartbeat/', views.heartbeat_curso, name='heartbeat'),
    path('<int:pk>/seccion/<int:seccion_id>/completar/', views.marcar_completada, name='marcar_completada'),
    # Evaluaciones
    path('admin/<int:pk>/evaluacion/', views.admin_evaluaciones, name='admin_evaluaciones'),
    path('admin/evaluacion/<int:eval_id>/', views.admin_evaluacion_editar, name='admin_evaluacion_editar'),
    path('admin/evaluacion/<int:eval_id>/pregunta/agregar/', views.api_agregar_pregunta, name='api_agregar_pregunta'),
    path('admin/evaluacion/<int:eval_id>/pregunta/<int:preg_id>/eliminar/', views.api_eliminar_pregunta, name='api_eliminar_pregunta'),
    path('admin/evaluacion/<int:eval_id>/pregunta/<int:preg_id>/opcion/agregar/', views.api_agregar_opcion, name='api_agregar_opcion'),
    path('admin/evaluacion/<int:eval_id>/pregunta/<int:preg_id>/opcion/<int:op_id>/eliminar/', views.api_eliminar_opcion, name='api_eliminar_opcion'),
    # Estudiante
    path('<int:pk>/evaluacion/<int:eval_id>/datos/', views.api_datos_evaluacion, name='api_datos_evaluacion'),
    path('<int:pk>/evaluacion/<int:eval_id>/iniciar/', views.iniciar_evaluacion, name='iniciar_evaluacion'),
    path('<int:pk>/evaluacion/<int:eval_id>/responder/', views.api_responder_pregunta, name='api_responder_pregunta'),
    path('<int:pk>/evaluacion/<int:eval_id>/finalizar/', views.finalizar_evaluacion, name='finalizar_evaluacion'),
    path('reporte-equipo/', views.reporte_equipo, name='reporte_equipo'),
    path('mis-cursos/', views.mis_cursos_realizados, name='mis_cursos_realizados'),
]
