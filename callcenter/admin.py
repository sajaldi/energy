from django.contrib import admin
from .models import SolicitudTicket

from django.urls import path
from .views import trigger_sync_tickets

@admin.register(SolicitudTicket)
class SolicitudTicketAdmin(admin.ModelAdmin):
    list_display = ('folio', 'id_solicitud', 'solicitante', 'ubicacion', 'servicio', 'area', 'activo', 'fecha_solicitud')
    list_filter = ('servicio', 'area', 'tipo_solicitud', 'fecha_solicitud', 'ubicacion', ('activo', admin.RelatedOnlyFieldListFilter))
    search_fields = ('folio', 'id_solicitud', 'solicitante', 'solicitud_descripcion', 'diagnostico', 'activo__nombre', 'activo__codigo_interno')
    autocomplete_fields = ('activo',)
    date_hierarchy = 'fecha_solicitud'
    readonly_fields = ('creado_en', 'actualizado_en')
    
    # Optimización de Performance
    list_select_related = ('activo', 'ubicacion')
    list_per_page = 25
    show_full_result_count = False # Evita el COUNT(*) lento en tablas grandes
    
    def get_queryset(self, request):
        # Seleccionar solo los campos necesarios para la lista unificada
        return super().get_queryset(request).select_related('activo', 'ubicacion').only(
            'id', 'folio', 'id_solicitud', 'solicitante', 'servicio', 'area', 
            'activo__nombre', 'activo__codigo_interno', 'fecha_solicitud', 'tipo_solicitud',
            'ubicacion__nombre'
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('sync-tickets/', self.admin_site.admin_view(trigger_sync_tickets), name='sync-tickets'),
        ]
        return custom_urls + urls
