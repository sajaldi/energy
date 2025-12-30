from django.urls import path
from . import views

app_name = 'mantenimiento'

urlpatterns = [
    path('calendario/', views.calendario_mantenimiento, name='calendario'),
    path('calendario/detallado/', views.calendario_detallado, name='detallado'),
    path('cronograma/', views.cronograma_mantenimiento_visual, name='cronograma'),
]
