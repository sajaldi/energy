from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Documento, Revision, TipoDocumento, Disciplina, MetadatoConfig, MetadatoValor, ComentarioDocumento
import json

from django.forms import TextInput, Textarea
from django.db import models

class ComentarioDocumentoInline(admin.TabularInline):
    model = ComentarioDocumento
    extra = 0
    fields = ('usuario', 'texto', 'pagina', 'resuelto')
    readonly_fields = ('usuario', 'texto', 'pagina')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False # Se agregan desde el visor

class RevisionInline(admin.TabularInline):
    model = Revision
    extra = 1
    # Campos minimalistas para la lista: Versión, Archivo, Comentario (opcional), Fecha
    fields = ('revision', 'archivo', 'fecha_revision', 'comentarios')
    readonly_fields = ('fecha_revision',) 
    
    # Reducir tamaño del campo comentarios para que parezca una fila de tabla limpia
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': '10'})},
        models.TextField: {'widget': Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'resize:none;'})},
    }

    def has_add_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return True

class MetadatoValorInline(admin.TabularInline):
    model = MetadatoValor
    extra = 0
    fields = ('get_etiqueta', 'valor')
    readonly_fields = ('get_etiqueta',)
    
    def get_etiqueta(self, obj):
        return obj.config.etiqueta if obj.config else "-"
    get_etiqueta.short_description = "Campo"

    def has_add_permission(self, request, obj=None):
        return False # Se crean dinámicamente

@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'titulo', 'tipo_documento', 'estado_actual', 'get_ultima_revision_info', 'trazabilidad_link', 'extraer_datos_button', 'solicitar_firmas_link')
    list_filter = ('tipo_documento', 'disciplina', 'estado_actual')
    search_fields = ('codigo', 'titulo', 'revisiones__comentarios')
    
    inlines = [MetadatoValorInline, ComentarioDocumentoInline, RevisionInline]
    autocomplete_fields = ('activos', 'ubicaciones')
    change_list_template = "admin/documentos/documento/change_list.html"
    
    def add_view(self, request, form_url='', extra_context=None):
        from django.shortcuts import redirect
        return redirect('documentos:documento_wizard')

    fieldsets = (
        ('Identificación', {
            'fields': (('codigo', 'titulo'), ('tipo_documento', 'disciplina'), ('respuesta_a', 'trazabilidad_link'))
        }),
        ('Estado', {
            'fields': ('estado_actual', 'ultima_revision', 'extraer_datos_button')
        }),
        ('Relaciones', {
            'fields': ('activos', 'ubicaciones')
        }),
    )
    
    readonly_fields = ('ultima_revision', 'extraer_datos_button', 'trazabilidad_link') 

    def trazabilidad_link(self, obj):
        if not obj.pk: return "-"
        url = reverse('documentos:documento_trazabilidad', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="background: #0f172a; color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-weight: 700; font-size: 0.8rem;">🌳 Ver Trazabilidad</a>',
            url
        )
    trazabilidad_link.short_description = "Flujo / Trazabilidad"
    
    def save_formset(self, request, form, formset, change):
        # Asignar usuario automáticamente a las revisiones nuevas
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, Revision) and not instance.pk:
                instance.creado_por = request.user
            instance.save()
        formset.save_m2m()

    def extraer_datos_button(self, obj):
        if not obj.pk: return "-"
        url = reverse('documentos:documento_reprocesar', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="background: #4f46e5; color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-weight: 700; font-size: 0.8rem;">🔍 Extraer Info</a>',
            url
        )
    extraer_datos_button.short_description = "Análisis"
    
    def get_ultima_revision_info(self, obj):
        if obj.ultima_revision:
            return format_html(
                '<b>Rev {}</b> <br> <small>{}</small>', 
                obj.ultima_revision.revision,
                obj.ultima_revision.fecha_revision
            )
        return "Sin Versión"
    get_ultima_revision_info.short_description = "Versión Actual"

    def get_extraccion_status(self, obj):
        if obj.ultima_revision:
            status = obj.ultima_revision.estado_extraccion
            color = {
                'PENDIENTE': '#64748b',
                'PROCESANDO': '#2563eb',
                'COMPLETADO': '#10b981',
                'ERROR': '#ef4444',
                'NO_APLICA': '#94a3b8'
            }.get(status, '#000')
            
            return format_html(
                '<span style="background: {}15; color: {}; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.75rem;">{}</span>',
                color, color, status
            )
        return "-"
    get_extraccion_status.short_description = "Extracción"
    
    def solicitar_firmas_link(self, obj):
        """Link para solicitar firmas para este documento"""
        from django.urls import reverse
        url = reverse('firmas:solicitar_firmas', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: 600;">🖊️ Solicitar Firmas</a>',
            url
        )
    solicitar_firmas_link.short_description = "Firmas"

class MetadatoConfigInline(admin.TabularInline):
    model = MetadatoConfig
    extra = 1

@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo')
    inlines = [MetadatoConfigInline]

@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo')
    search_fields = ('nombre', 'codigo')

@admin.register(Revision)
class RevisionAdmin(admin.ModelAdmin):
    list_display = ('documento', 'revision', 'fecha_revision', 'creado_por', 'estado_extraccion', 'get_datos_preview')
    list_filter = ('fecha_revision', 'creado_por', 'estado_extraccion')
    search_fields = ('documento__codigo', 'datos_extraidos')
    date_hierarchy = 'fecha_revision'
    readonly_fields = ('datos_extraidos', 'estado_extraccion')
    change_list_template = "admin/documentos/revision/change_list.html"

    def get_datos_preview(self, obj):
        if obj.datos_extraidos:
            return format_html(
                '<pre style="max-width: 300px; max-height: 100px; overflow: auto; font-size: 0.7rem;">{}</pre>',
                json.dumps(obj.datos_extraidos, indent=2, ensure_ascii=False)
            )
        return "-"
    get_datos_preview.short_description = "Datos Extraídos"

@admin.register(ComentarioDocumento)
class ComentarioDocumentoAdmin(admin.ModelAdmin):
    list_display = ('documento', 'usuario', 'texto_resumen', 'pagina', 'creado_en', 'resuelto')
    list_filter = ('resuelto', 'creado_en', 'usuario')
    search_fields = ('documento__codigo', 'texto', 'usuario__username')
    readonly_fields = ('creado_en',)
    
    def texto_resumen(self, obj):
        return obj.texto[:50] + "..." if len(obj.texto) > 50 else obj.texto
    texto_resumen.short_description = "Comentario"

# Importar y registrar admins del sistema de firmas
from . import admin_firmas

