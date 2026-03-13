from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import TipoComunicado, Comunicado, Destinatario, AdjuntoComunicado, Notificacion, BotSession

class DestinatarioInline(admin.TabularInline):
    model = Destinatario
    extra = 1
    autocomplete_fields = ['usuario']

class AdjuntoInline(admin.TabularInline):
    model = AdjuntoComunicado
    extra = 1
    autocomplete_fields = ['documento_revision', 'activo']

@admin.register(TipoComunicado)
class TipoComunicadoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo')
    search_fields = ('nombre', 'codigo')

@admin.register(Comunicado)
class ComunicadoAdmin(admin.ModelAdmin):
    list_display = ('consecutivo', 'asunto', 'tipo', 'remitente', 'fecha_envio', 'get_estado_html', 'get_responder_button')
    list_filter = ('tipo', 'estado', 'fecha_envio')
    search_fields = ('consecutivo', 'asunto', 'cuerpo')
    readonly_fields = ('consecutivo', 'remitente', 'fecha_envio', 'get_responder_button')
    inlines = [DestinatarioInline, AdjuntoInline]
    
    actions = ['enviar_comunicado']

    def get_responder_button(self, obj):
        if obj and obj.estado == 'ENVIADO':
            url = f"/admin/comunicaciones/comunicado/add/?parent_id={obj.pk}"
            return format_html(
                '<a href="{}" class="button" style="background: #007bff; color: white; padding: 5px 15px; border-radius: 4px; text-decoration: none;">'
                '<i class="fas fa-reply"></i> Responder</a>',
                url
            )
        return "-"
    get_responder_button.short_description = "Acción"

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        parent_id = request.GET.get('parent_id')
        if parent_id:
            try:
                parent = Comunicado.objects.get(pk=parent_id)
                initial['parent'] = parent.pk
                initial['tipo'] = parent.tipo.pk
                initial['asunto'] = f"RE: {parent.asunto}"
                # Nota: Los destinatarios (Inlines) se manejan mejor en save_model o get_formsets
            except Comunicado.DoesNotExist:
                pass
        return initial

    def get_estado_html(self, obj):
        colors = {
            'BORRADOR': '#6c757d',
            'ENVIADO': '#28a745',
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{}</span>',
            colors.get(obj.estado, '#000'),
            obj.get_estado_display()
        )
    get_estado_html.short_description = "Estado"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.remitente = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Enviar comunicados seleccionados")
    def enviar_comunicado(self, request, queryset):
        for obj in queryset.filter(estado='BORRADOR'):
            obj.estado = 'ENVIADO'
            obj.save() # El método save del modelo genera el consecutivo
        self.message_user(request, "Los comunicados seleccionados han sido enviados y ahora son inmutables.")

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.estado == 'ENVIADO':
            # Si ya fue enviado, TODO es de solo lectura (Aconex Style)
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields

@admin.register(Destinatario)
class DestinatarioAdmin(admin.ModelAdmin):
    list_display = ('comunicado', 'usuario', 'tipo', 'leido', 'fecha_leido')
    list_filter = ('tipo', 'leido')
    search_fields = ('comunicado__asunto', 'usuario__username')

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'comunicado', 'leida', 'fecha_creacion')
    list_filter = ('leida', 'fecha_creacion')
    search_fields = ('usuario__username', 'comunicado__asunto')
    readonly_fields = ('fecha_creacion',)

@admin.register(BotSession)
class BotSessionAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'status', 'last_update')
    search_fields = ('phone_number', 'status')
    list_filter = ('status', 'last_update')
    readonly_fields = ('last_update',)
