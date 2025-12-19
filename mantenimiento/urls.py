from django.urls import path
from . import views

app_name = 'mantenimiento'

urlpatterns = [
    path('calendario/', views.calendario_mantenimiento, name='calendario'),
]
