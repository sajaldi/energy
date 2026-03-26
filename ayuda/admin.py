from django.contrib import admin
from .models import CategoriaAyuda, ArticuloAyuda

@admin.register(CategoriaAyuda)
class CategoriaAyudaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'icono', 'orden')
    search_fields = ('nombre',)

@admin.register(ArticuloAyuda)
class ArticuloAyudaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'categoria', 'app_label', 'model_name', 'es_contextual')
    list_filter = ('categoria', 'es_contextual', 'app_label')
    search_fields = ('titulo', 'contenido')
    prepopulated_fields = {'slug': ('titulo',)}
    fieldsets = (
        (None, {
            'fields': ('categoria', 'titulo', 'slug', 'contenido', 'video_url')
        }),
        ('Contexto Admin (Ayuda Personalizada)', {
            'fields': ('app_label', 'model_name', 'es_contextual'),
            'description': 'Configure estos campos si desea que el artículo aparezca automáticamente al navegar en una sección específica.'
        }),
    )
