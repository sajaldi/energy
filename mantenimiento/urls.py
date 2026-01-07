from django.urls import path
from . import views

app_name = 'mantenimiento'

urlpatterns = [
    path('calendario/', views.calendario_mantenimiento, name='calendario'),
    path('calendario/detallado/', views.calendario_detallado, name='detallado'),
    path('cronograma/', views.cronograma_mantenimiento_visual, name='cronograma'),
    path('cronograma/<int:year>/<int:month>/', views.detalle_mes, name='detalle_mes'),
    path('api/update-ot-date/', views.api_update_ot_date, name='api_update_ot_date'),
    path('api/split-ot-asset/', views.api_split_ot_asset, name='api_split_ot_asset'),
    path('api/merge-ots/', views.api_merge_ots, name='api_merge_ots'),
    path('api/bulk-update-ot-dates/', views.api_bulk_update_ot_dates, name='api_bulk_update_ot_dates'),
    path('api/delete-ots/', views.api_delete_ots, name='api_delete_ots'),
    path('api/notifications/', views.api_get_notifications, name='api_get_notifications'),
    path('api/notifications/read/', views.api_mark_notification_read, name='api_mark_notification_read'),
    path('programar-rutina/', views.programar_rutina_wizard, name='programar_rutina_wizard'),
    path('api/get-assets-wizard/', views.api_get_assets_wizard, name='api_get_assets_wizard'),
]
