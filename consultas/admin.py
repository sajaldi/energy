from django.contrib import admin
from .models import Consulta, MensajeConsulta


class MensajeInline(admin.TabularInline):
    model = MensajeConsulta
    extra = 0
    readonly_fields = ('fecha_str', 'hora_str', 'remitente', 'texto', 'linea_original')
    fields = ('fecha_str', 'hora_str', 'remitente', 'texto')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'subido_por', 'total_mensajes', 'procesado', 'creado_en')
    list_filter = ('procesado', 'creado_en')
    search_fields = ('nombre',)
    readonly_fields = ('procesado', 'total_mensajes', 'creado_en')
    inlines = [MensajeInline]

    def save_model(self, request, obj, form, change):
        if not obj.subido_por:
            obj.subido_por = request.user
        super().save_model(request, obj, form, change)
        
        # Procesar automáticamente al subir
        if not change or not obj.procesado:
            obj.procesar_archivo()


@admin.register(MensajeConsulta)
class MensajeConsultaAdmin(admin.ModelAdmin):
    list_display = ('fecha_str', 'hora_str', 'remitente', 'texto_corto', 'consulta')
    list_filter = ('consulta', 'remitente')
    search_fields = ('remitente', 'texto', 'linea_original')
    readonly_fields = ('consulta', 'fecha_str', 'hora_str', 'remitente', 'texto', 'linea_original')

    def texto_corto(self, obj):
        return obj.texto[:80] + '...' if len(obj.texto) > 80 else obj.texto
    texto_corto.short_description = "Texto"
