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
    path('proxy/pdf/<int:doc_id>/', views.documento_proxy_pdf, name='documento_proxy_pdf'),
    path('api/detalle/<int:doc_id>/', views.documento_detalle_json, name='documento_detalle_json'),
    path('api/comentar/<int:doc_id>/', views.documento_comentar, name='documento_comentar'),
    path('api/comentar/u/<int:comentario_id>/', views.documento_editar_comentario, name='documento_editar_comentario'),
    path('api/comentar/d/<int:comentario_id>/', views.documento_eliminar_comentario, name='documento_eliminar_comentario'),
    path('api/actualizar-estado/<int:doc_id>/', views.documento_actualizar_estado, name='documento_actualizar_estado'),
    path('api/actualizar-responsable/<int:doc_id>/', views.documento_actualizar_responsable, name='documento_actualizar_responsable'),
    path('api/buscar/', views.documento_buscar, name='documento_buscar'),
    path('api/chat-ia/', views.documento_chat_ia, name='documento_chat_ia'),
    path('api/trigger-extraction/<int:doc_id>/', views.trigger_n8n_extraction, name='trigger_n8n_extraction'),
    path('api/update-texto/<int:doc_id>/', views.update_documento_texto, name='update_documento_texto'),
]
