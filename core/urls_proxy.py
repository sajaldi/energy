from django.urls import path
from .views_proxy import media_proxy

urlpatterns = [
    path('', media_proxy, name='media_proxy'),
]
