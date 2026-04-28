from django.urls import path
from . import views

app_name = 'iot'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('sync-device/<int:device_id>/', views.sync_device, name='sync_device'),
]
