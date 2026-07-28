from django.urls import path
from . import views

app_name = 'consultas'

urlpatterns = [
    path('', views.lista_consultas, name='lista'),
    path('subir/', views.subir_consulta, name='subir'),
    path('<int:consulta_id>/', views.detalle_consulta, name='detalle'),
    path('<int:consulta_id>/buscar/', views.buscar_mensajes, name='buscar'),
    path('<int:consulta_id>/chat/', views.chat_ia, name='chat_ia'),
    path('<int:consulta_id>/generar-embeddings/', views.generar_embeddings_stream, name='generar_embeddings'),
]
