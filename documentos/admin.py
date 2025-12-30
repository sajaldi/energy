from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Documento, Revision, TipoDocumento, Disciplina

from django.forms import TextInput, Textarea
from django.db import models

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

@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'titulo', 'tipo_documento', 'disciplina', 'estado_actual', 'get_ultima_revision_info', 'solicitar_firmas_link')
    list_filter = ('tipo_documento', 'disciplina', 'estado_actual')
    search_fields = ('codigo', 'titulo', 'revisiones__comentarios')
    
    inlines = [RevisionInline]
    
    fieldsets = (
        ('Identificación', {
            'fields': (('codigo', 'titulo'), ('tipo_documento', 'disciplina'))
        }),
        ('Estado', {
            'fields': ('estado_actual', 'ultima_revision')
        }),
        ('Relaciones', {
            'fields': ('activos', 'ubicaciones')
        }),
    )
    
    readonly_fields = ('ultima_revision',) 
    
    def save_formset(self, request, form, formset, change):
        # Asignar usuario automáticamente a las revisiones nuevas
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, Revision) and not instance.pk:
                instance.creado_por = request.user
            instance.save()
        formset.save_m2m()

    def get_ultima_revision_info(self, obj):
        if obj.ultima_revision:
            return format_html(
                '<b>Rev {}</b> <br> <small>{}</small>', 
                obj.ultima_revision.revision,
                obj.ultima_revision.fecha_revision
            )
        return "Sin Versión"
    get_ultima_revision_info.short_description = "Versión Actual"
    
    def solicitar_firmas_link(self, obj):
        """Link para solicitar firmas para este documento"""
        from django.urls import reverse
        url = reverse('firmas:solicitar_firmas', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: 600;">🖊️ Solicitar Firmas</a>',
            url
        )
    solicitar_firmas_link.short_description = "Firmas"

@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo')

@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo')
    search_fields = ('nombre', 'codigo')

@admin.register(Revision)
class RevisionAdmin(admin.ModelAdmin):
    list_display = ('documento', 'revision', 'fecha_revision', 'creado_por')
    list_filter = ('fecha_revision', 'creado_por')
    search_fields = ('documento__codigo',)
    date_hierarchy = 'fecha_revision'

# Importar y registrar admins del sistema de firmas
from . import admin_firmas

