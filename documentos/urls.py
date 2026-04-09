from django.urls import path
from . import views, views_wizard, views_bulk

app_name = 'documentos'

urlpatterns = [
    # Carga masiva (drag & drop)
    path('carga-masiva/', views_bulk.documento_carga_masiva, name='carga_masiva'),
    path('carga-masiva/submit/', views_bulk.documento_carga_masiva_submit, name='carga_masiva_submit'),
    # Wizard de creación de documentos
    path('nuevo/', views_wizard.documento_wizard, name='documento_wizard'),
    path('nuevo/status/<int:doc_id>/', views_wizard.documento_wizard_status, name='documento_wizard_status'),
    path('reprocesar/<int:doc_id>/', views_wizard.documento_reprocesar_verificacion, name='documento_reprocesar'),
    # Trazabilidad
    path('trazabilidad/<int:doc_id>/', views.documento_trazabilidad, name='documento_trazabilidad'),
    path('visor-pines/<int:doc_id>/', views.documento_visor_pines, name='visor_pines'),
    path('proxy/pdf/<int:doc_id>/', views.documento_proxy_pdf, name='documento_proxy_pdf'),
    path('api/detalle/<int:doc_id>/', views.documento_detalle_json, name='documento_detalle_json'),
    path('api/comentar/<int:doc_id>/', views.documento_comentar, name='documento_comentar'),
    path('api/comentar/u/<int:comentario_id>/', views.documento_editar_comentario, name='documento_editar_comentario'),
    path('api/comentar/d/<int:comentario_id>/', views.documento_eliminar_comentario, name='documento_eliminar_comentario'),
    path('api/comentar/toggle-resuelto/<int:comentario_id>/', views.documento_toggle_resuelto, name='documento_toggle_resuelto'),
    path('api/actualizar-estado/<int:doc_id>/', views.documento_actualizar_estado, name='documento_actualizar_estado'),
    path('api/actualizar-responsable/<int:doc_id>/', views.documento_actualizar_responsable, name='documento_actualizar_responsable'),
    path('api/actualizar-fecha/<int:doc_id>/', views.documento_actualizar_fecha, name='documento_actualizar_fecha'),
    path('api/buscar/', views.documento_buscar, name='documento_buscar'),
    path('api/chat-ia/', views.documento_chat_ia, name='documento_chat_ia'),
    path('api/test-n8n/', views.test_n8n_ping, name='test_n8n_ping'),
    path('api/trigger-extraction/<int:doc_id>/', views.trigger_n8n_extraction, name='trigger_n8n_extraction'),
    path('api/analizar-oficios/<int:doc_id>/', views.api_analizar_oficios_trazabilidad, name='api_analizar_oficios_trazabilidad'),
    path('api/analizar-biblioteca/<int:bib_id>/', views.api_analizar_biblioteca_ia, name='api_analizar_biblioteca_ia'),
    path('api/update-texto/<int:doc_id>/', views.update_documento_texto, name='update_documento_texto'),
    path('api/callback-procesamiento/<int:revision_id>/', views.callback_n8n_procesamiento, name='callback_n8n_procesamiento'),
    path('sync-metadatos/<int:doc_id>/', views.documento_sync_metadatos, name='documento_sync_metadatos'),
    path('api/bibliotecas/<int:doc_id>/', views.api_bibliotecas_list, name='api_bibliotecas_list'),
    path('api/bibliotecas/toggle/<int:doc_id>/<int:bib_id>/', views.api_biblioteca_toggle, name='api_biblioteca_toggle'),
    path('api/bibliotecas/documentos/<int:bib_id>/', views.api_biblioteca_documentos, name='api_biblioteca_documentos'),
    path('api/documento/status/<int:doc_id>/', views.api_documento_update_status, name='api_documento_update_status'),
    path('api/busqueda-vectorial/', views.api_documento_busqueda_vectorial, name='api_documento_busqueda_vectorial'),
    path('api/migrar-embeddings/', views.api_documento_migrar_embeddings, name='api_documento_migrar_embeddings'),
    path('api/vectorize/<int:doc_id>/', views.api_documento_vectorize_single, name='api_documento_vectorize_single'),
    path('busqueda-semantica/', views.busqueda_vectorial, name='busqueda_vectorial'),
    path('biblioteca/visualizar/<int:bib_id>/', views.biblioteca_visualizar, name='biblioteca_visualizar'),
    path('api/model-fields/', views.api_get_model_fields, name='api_get_model_fields'),
    path('api/metadato/u/<int:mv_id>/', views.api_actualizar_metadato, name='api_actualizar_metadato'),
    path('api/biblioteca/comentar/<int:bib_id>/', views.api_biblioteca_crear_comentario, name='api_biblioteca_crear_comentario'),
]
