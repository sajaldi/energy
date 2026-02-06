from django.urls import path
from . import views_mayan, views_wizard

app_name = 'documentos'

urlpatterns = [
    # API endpoints para Mayan
    path('api/mayan/upload/', views_mayan.upload_document_to_mayan, name='mayan_upload_document'),
    # Wizard de creación de documentos
    path('nuevo/', views_wizard.documento_wizard, name='documento_wizard'),
    path('reprocesar/<int:doc_id>/', views_wizard.documento_reprocesar_verificacion, name='documento_reprocesar'),
]
