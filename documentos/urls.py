from django.urls import path
from . import views, views_mayan, views_wizard

app_name = 'documentos'

urlpatterns = [
    # API endpoints para Mayan
    path('api/mayan/upload/', views_mayan.upload_document_to_mayan, name='mayan_upload_document'),
    # Wizard de creación de documentos
    path('nuevo/', views_wizard.documento_wizard, name='documento_wizard'),
    path('reprocesar/<int:doc_id>/', views_wizard.documento_reprocesar_verificacion, name='documento_reprocesar'),
    # Trazabilidad
    path('trazabilidad/<int:doc_id>/', views.documento_trazabilidad, name='documento_trazabilidad'),
    path('visor-pines/<int:doc_id>/', views.documento_visor_pines, name='visor_pines'),
    path('api/detalle/<int:doc_id>/', views.documento_detalle_json, name='documento_detalle_json'),
    path('api/comentar/<int:doc_id>/', views.documento_comentar, name='documento_comentar'),
    path('api/actualizar-estado/<int:doc_id>/', views.documento_actualizar_estado, name='documento_actualizar_estado'),
    path('api/actualizar-responsable/<int:doc_id>/', views.documento_actualizar_responsable, name='documento_actualizar_responsable'),
]
