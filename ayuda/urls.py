from django.urls import path
from . import views, views_api

app_name = 'ayuda'

urlpatterns = [
    path('', views.help_index, name='index'),
    path('articulo/<slug:slug>/', views.help_detail, name='detail'),
    path('api/check-context/', views_api.check_context_help, name='api_check_context'),
    path('admin/upload-image/', views.upload_image_admin, name='admin_upload_image'),
    
    # Editor Standalone
    path('editor/', views.help_editor, name='editor'),
    path('editor/get/', views.ajax_get_article, name='ajax_get_article'),
    path('editor/save/', views.ajax_save_article, name='ajax_save_article'),
    path('editor/create/', views.ajax_create_article, name='ajax_create_article'),
]
