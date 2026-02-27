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
]
