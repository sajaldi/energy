from django.urls import path
from . import views

app_name = 'seguridad'

urlpatterns = [
    path('permiso/generar/ot/<int:ot_id>/', views.generar_permiso_de_ot, name='generar_permiso_ot'),
    path('permiso/<int:permiso_id>/', views.detalle_permiso_view, name='detalle_permiso'),
    
    # Mobile views
    path('app/permisos/', views.mobile_mis_permisos, name='mobile_mis_permisos'),
    path('app/permiso/<int:pk>/', views.mobile_permiso_detalle, name='mobile_permiso_detalle'),
    path('app/permiso/generar/<int:ot_id>/', views.mobile_generar_permiso, name='mobile_generar_permiso'),
    path('app/permiso/pdf/<int:permiso_id>/', views.generar_permiso_pdf_view, name='mobile_permiso_pdf'),
]
