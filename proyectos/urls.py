from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
    path('api/crear-actividad/', views.crear_actividad_api, name='crear_actividad_api'),
]
