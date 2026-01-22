from django.contrib import admin
from .models import SolicitudTicket

@admin.register(SolicitudTicket)
class SolicitudTicketAdmin(admin.ModelAdmin):
    list_display = ('folio', 'id_solicitud', 'solicitante', 'servicio', 'area', 'fecha_solicitud', 'tipo_solicitud')
    list_filter = ('servicio', 'area', 'tipo_solicitud', 'fecha_solicitud')
    search_fields = ('folio', 'id_solicitud', 'solicitante', 'solicitud_descripcion', 'diagnostico')
    date_hierarchy = 'fecha_solicitud'
    readonly_fields = ('creado_en', 'actualizado_en')
