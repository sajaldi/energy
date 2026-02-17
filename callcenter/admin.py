from django.contrib import admin
from .models import SolicitudTicket

from django.urls import path
from .views import trigger_sync_tickets

@admin.register(SolicitudTicket)
class SolicitudTicketAdmin(admin.ModelAdmin):
    list_display = ('folio', 'id_solicitud', 'solicitante', 'servicio', 'area', 'activo', 'fecha_solicitud', 'tipo_solicitud')
    list_filter = ('servicio', 'area', 'tipo_solicitud', 'fecha_solicitud', 'activo')
    search_fields = ('folio', 'id_solicitud', 'solicitante', 'solicitud_descripcion', 'diagnostico', 'activo__nombre', 'activo__codigo_interno')
    autocomplete_fields = ('activo',)
    date_hierarchy = 'fecha_solicitud'
    readonly_fields = ('creado_en', 'actualizado_en')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('sync-tickets/', self.admin_site.admin_view(trigger_sync_tickets), name='sync-tickets'),
        ]
        return custom_urls + urls
