from django.urls import path
from . import views

urlpatterns = [
    path('registrar-salida/', views.registrar_salida_view, name='registrar_salida'),
    path('api/stock/<int:material_id>/', views.api_get_material_stock, name='api_get_material_stock'),
]
