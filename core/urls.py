from django.urls import path
from . import views

urlpatterns = [
    path('import-consumo/', views.import_excel, name='import_consumo'),
    path('admin-menu/', views.admin_menu, name='admin_menu'),  # New entry
]