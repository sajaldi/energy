from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.html import format_html
from .models import PlantillaWord


@admin.register(PlantillaWord)
class PlantillaWordAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'content_type', 'activa', 'creado_en', 'btn_exportar_ejemplo')
    list_filter = ('activa', 'content_type')
    search_fields = ('nombre', 'descripcion')
    readonly_fields = ('creado_en', 'actualizado_en', 'btn_descargar_plantilla_blank')
    autocomplete_fields = []

    fieldsets = (
        ('Información', {
            'fields': ('nombre', 'descripcion', 'content_type', 'activa')
        }),
        ('Archivo de Plantilla', {
            'fields': ('archivo', 'btn_descargar_plantilla_blank'),
            'description': (
                'Sube aquí la plantilla Word (.docx) diseñada por ti. '
                'Si aún no tienes la plantilla, usa el botón para descargarla en blanco, '
                'diseñala en Word y luego sube el resultado.'
            )
        }),
        ('Metadata', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )

    def btn_descargar_plantilla_blank(self, obj):
        if obj and obj.content_type_id:
            url = reverse('plantillas:generar', args=[obj.content_type_id])
            return format_html(
                '<a class="button" href="{}" target="_blank">'
                '⬇️ Descargar plantilla en blanco ({{ campos }})</a>',
                url
            )
        return "Selecciona un Modelo primero y guarda."
    btn_descargar_plantilla_blank.short_description = "Descargar plantilla base"

    def btn_exportar_ejemplo(self, obj):
        """Muestra link a la vista de exportación (requiere un registro_pk)"""
        if obj.archivo:
            ct = obj.content_type
            return format_html(
                '<small style="color:#888">Usa el botón en el registro de {}</small>',
                ct.model
            )
        return format_html('<small style="color:#ccc">Sin archivo</small>')
    btn_exportar_ejemplo.short_description = "Exportar"


class TemplateExportMixin:
    """
    Mixin para usar en cualquier ModelAdmin que desee mostrar botones de 
    exportación a Word usando las plantillas configuradas.
    """
    def get_word_templates_buttons(self, obj):
        if not obj.pk:
            return "-"
        
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(obj)
        plantillas = PlantillaWord.objects.filter(content_type=ct, activa=True)
        
        if not plantillas.exists():
            return format_html(
                '<span style="color: #94a3b8; font-size: 0.8rem;">Sin plantillas. '
                '<a href="{}?content_type={}" style="text-decoration:underline;">Crear una</a></span>',
                reverse('admin:plantillas_plantillaword_add'),
                ct.id
            )
        
        links = []
        for p in plantillas:
            url = reverse('plantillas:exportar', args=[
                p.pk, ct.app_label, ct.model, obj.pk
            ])
            links.append(format_html(
                '<a class="button" href="{}" style="margin-right:5px; margin-bottom:5px; '
                'background: #1e293b; color: white; padding: 5px 10px; border-radius: 4px; '
                'text-decoration: none; display: inline-block;">📄 {}</a>',
                url, p.nombre
            ))
            
        return format_html(''.join(links))
    
    get_word_templates_buttons.short_description = "Exportar a Word"
