from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from mptt.admin import DraggableMPTTAdmin
from .models import Activo, Categoria, Ubicacion

@admin.register(Categoria)
class CategoriaAdmin(ImportExportModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

@admin.register(Ubicacion)
class UbicacionAdmin(DraggableMPTTAdmin):
    mptt_indent_field = "nombre"
    list_display = ('tree_actions', 'indented_title', 'descripcion')
    list_display_links = ('indented_title',)
    search_fields = ('nombre',)
    list_filter = ('padre',)

@admin.register(Activo)
class ActivoAdmin(ImportExportModelAdmin):
    list_display = ('codigo_interno', 'nombre', 'marca', 'modelo', 'serie', 'categoria', 'estado', 'ubicacion', 'responsable')
    list_filter = ('estado', 'categoria', 'marca', 'creado_en', 'ubicacion')
    search_fields = ('nombre', 'codigo_interno', 'serie', 'marca', 'modelo', 'ubicacion__nombre', 'ubicacion_legacy')
    readonly_fields = ('creado_en', 'actualizado_en')
    
    fieldsets = (
        ('Identificación', {
            'fields': ('nombre', 'codigo_interno', 'serie', 'categoria')
        }),
        ('Detalles Técnicos', {
            'fields': ('marca', 'modelo', 'descripcion', 'foto')
        }),
        ('Estado y Ubicación', {
            'fields': ('estado', 'ubicacion', 'ubicacion_legacy', 'responsable')
        }),
        ('Información Financiera', {
            'fields': ('fecha_compra', 'costo')
        }),
        ('Sistema', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )
