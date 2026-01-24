from django.urls import path
from . import views_mayan
# Si tienes otras vistas existentes, impórtalas también
# from . import views

app_name = 'documentos'

urlpatterns = [
    # API endpoints para Mayan
    path('api/mayan/upload/', views_mayan.upload_document_to_mayan, name='mayan_upload_document'),
    # path('api/mayan/token/', views_mayan.get_mayan_token, name='mayan_get_token'), # Futuro
]
