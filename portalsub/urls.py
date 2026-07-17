from django.urls import path
from . import views
from notificaciones.views import portal_notificaciones

app_name = 'portalsub'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('expediente/', views.expediente, name='expediente'),
    path('expediente/<int:mes>/<int:anio>/', views.expediente_mes, name='expediente_mes'),
    path('expediente/<int:mes>/<int:anio>/subir/', views.subir_documento, name='subir_documento'),
    path('expediente/<int:mes>/<int:anio>/enviar/', views.enviar_expediente, name='enviar_expediente'),
    path('entregable/subir/', views.subir_entregable, name='subir_entregable'),
    path('entregable/<int:doc_id>/eliminar/', views.eliminar_entregable, name='eliminar_entregable'),
    path('personal/', views.personal_list, name='personal_list'),
    path('personal/nuevo/', views.personal_crear, name='personal_crear'),
    path('personal/<int:pk>/editar/', views.personal_editar, name='personal_editar'),
    path('personal/<int:pk>/eliminar/', views.personal_eliminar, name='personal_eliminar'),
    path('personal/reporte-altas-bajas/', views.reporte_altas_bajas, name='reporte_altas_bajas'),
    path('personal/<int:pk>/', views.personal_detalle, name='personal_detalle'),
    path('personal/<int:pk>/subir-documento/', views.subir_documento_personal, name='subir_documento_personal'),
    path('personal/<int:pk>/documento/<int:doc_id>/eliminar/', views.eliminar_documento_personal, name='eliminar_documento_personal'),
    path('ordenes/', views.ordenes_list, name='ordenes_list'),
    path('ordenes/<int:oc_id>/', views.orden_detalle, name='orden_detalle'),
    path('ordenes/<int:oc_id>/subir/', views.subir_documento_oc, name='subir_documento_oc'),
    path('ordenes/<int:oc_id>/documento/<int:doc_id>/eliminar/', views.eliminar_documento_oc, name='eliminar_documento_oc'),
    path('notificaciones/', portal_notificaciones, name='notificaciones'),
]
