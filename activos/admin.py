from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Activo, Categoria

@admin.register(Categoria)
class CategoriaAdmin(ImportExportModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

@admin.register(Activo)
class ActivoAdmin(ImportExportModelAdmin):
    list_display = ('codigo_interno', 'nombre', 'marca', 'modelo', 'serie', 'categoria', 'estado', 'ubicacion', 'responsable')
    list_filter = ('estado', 'categoria', 'marca', 'creado_en')
    search_fields = ('nombre', 'codigo_interno', 'serie', 'marca', 'modelo', 'ubicacion')
    readonly_fields = ('creado_en', 'actualizado_en')
    
    fieldsets = (
        ('Identificación', {
            'fields': ('nombre', 'codigo_interno', 'serie', 'categoria')
        }),
        ('Detalles Técnicos', {
            'fields': ('marca', 'modelo', 'descripcion', 'foto')
        }),
        ('Estado y Ubicación', {
            'fields': ('estado', 'ubicacion', 'responsable')
        }),
        ('Información Financiera', {
            'fields': ('fecha_compra', 'costo')
        }),
        ('Sistema', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )
