from django.urls import path
from . import views

app_name = 'costos'

urlpatterns = [
    path('', views.AnalisisListView.as_view(), name='analisis_list'),
    path('crear/', views.AnalisisCreateView.as_view(), name='analisis_create'),
    path('<int:pk>/', views.AnalisisDetailView.as_view(), name='analisis_detail'),
    path('<int:pk>/editar/', views.AnalisisUpdateView.as_view(), name='analisis_update'),
    path('<int:pk>/eliminar/', views.AnalisisDeleteView.as_view(), name='analisis_delete'),
    path('<int:pk>/aprobar/', views.AprobarAnalisisView.as_view(), name='analisis_aprobar'),
    path('<int:pk>/clonar/', views.ClonarAnalisisView.as_view(), name='analisis_clonar'),
    path('<int:pk>/detalle/agregar/', views.DetalleCreateView.as_view(), name='detalle_create'),
    path('<int:pk>/detalle/<int:detalle_pk>/editar/', views.DetalleUpdateView.as_view(), name='detalle_update'),
    path('<int:pk>/detalle/<int:detalle_pk>/eliminar/', views.DetalleDeleteView.as_view(), name='detalle_delete'),
    path('<int:pk>/factor/agregar/', views.FactorCreateView.as_view(), name='factor_create'),
    path('<int:pk>/factor/<int:factor_pk>/editar/', views.FactorUpdateView.as_view(), name='factor_update'),
    path('<int:pk>/factor/<int:factor_pk>/eliminar/', views.FactorDeleteView.as_view(), name='factor_delete'),
]
