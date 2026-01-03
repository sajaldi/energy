from django.urls import path
from . import views

app_name = 'presupuestos'

urlpatterns = [
    path('matriz/', views.presupuesto_matrix, name='matriz'),
    path('matriz/<int:pk>/', views.presupuesto_matrix, name='matriz_detalle'),
]
