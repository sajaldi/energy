from django.urls import path
from . import views, views_api

app_name = 'ayuda'

urlpatterns = [
    path('', views.help_index, name='index'),
    path('articulo/<slug:slug>/', views.help_detail, name='detail'),
    path('api/check-context/', views_api.check_context_help, name='api_check_context'),
]
