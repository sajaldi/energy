from django.contrib import admin
from django.utils.html import format_html
from .models import CategoriaAyuda, ArticuloAyuda

@admin.register(CategoriaAyuda)
class CategoriaAyudaAdmin(admin.ModelAdmin):
    list_display = ('nombre_con_icono', 'orden', 'total_articulos')
    list_editable = ('orden',)
    search_fields = ('nombre',)

    def nombre_con_icono(self, obj):
        return format_html('<i class="{} mr-2"></i> {}', obj.icono, obj.nombre)
    nombre_con_icono.short_description = "Categoría"

    def total_articulos(self, obj):
        return obj.articulos.count()
    total_articulos.short_description = "Artículos"

@admin.register(ArticuloAyuda)
class ArticuloAyudaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'categoria_icono', 'app_label', 'model_name', 'es_contextual', 'fecha_actualizacion')
    list_filter = ('categoria', 'es_contextual', 'app_label')
    search_fields = ('titulo', 'contenido')
    prepopulated_fields = {'slug': ('titulo',)}
    list_select_related = ('categoria',)
    
    fieldsets = (
        (None, {
            'fields': ('categoria', 'titulo', 'slug')
        }),
        ('Contenido del Artículo', {
            'fields': ('contenido', 'video_url'),
            'description': 'Escriba el contenido en formato Markdown. Se cargará un editor enriquecido.'
        }),
        ('Contexto Admin (Ayuda Contextual)', {
            'fields': (('app_label', 'model_name'), 'es_contextual'),
            'classes': ('collapse',),
            'description': 'Especifique para qué sección del sistema es esta ayuda.'
        }),
    )

    def categoria_icono(self, obj):
        return format_html('<i class="{} mr-1 text-muted"></i> {}', obj.categoria.icono, obj.categoria.nombre)
    categoria_icono.short_description = "Categoría"

    class Media:
        css = {
            'all': [
                'https://cdn.jsdelivr.net/simplemde/latest/simplemde.min.css',
                'core/css/admin_custom.css',
            ]
        }
        js = [
            'https://cdn.jsdelivr.net/simplemde/latest/simplemde.min.js',
            'ayuda/js/ayuda_admin.js',
        ]
