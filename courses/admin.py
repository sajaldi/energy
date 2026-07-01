from django.contrib import admin
from .models import Curso, Seccion, Pagina, AsignacionCurso, ProgresoSeccion, RegistroTiempo


class SeccionInline(admin.StackedInline):
    model = Seccion
    extra = 1
    fields = ('orden', 'titulo', 'contenido_html', 'duracion_minutos', 'obligatorio')


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'total_secciones', 'disponible_para_todos', 'activo', 'creado_en')
    list_filter = ('activo', 'disponible_para_todos')
    search_fields = ('titulo', 'descripcion')
    inlines = [SeccionInline]


@admin.register(Seccion)
class SeccionAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'curso', 'orden', 'obligatorio')
    list_filter = ('curso', 'obligatorio')
    search_fields = ('titulo', 'curso__titulo')
    autocomplete_fields = ('curso',)


@admin.register(Pagina)
class PaginaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'seccion', 'orden', 'obligatorio')
    list_filter = ('seccion__curso', 'obligatorio')
    search_fields = ('titulo', 'seccion__titulo')
    autocomplete_fields = ('seccion',)


@admin.register(AsignacionCurso)
class AsignacionCursoAdmin(admin.ModelAdmin):
    list_display = ('curso', 'usuario', 'grupo', 'completado', 'fecha_asignacion', 'fecha_vencimiento')
    list_filter = ('completado', 'curso')
    search_fields = ('curso__titulo', 'usuario__username', 'grupo__name')
    autocomplete_fields = ('usuario', 'grupo', 'asignado_por')


@admin.register(ProgresoSeccion)
class ProgresoSeccionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'seccion', 'asignacion', 'completado', 'completado_en')
    list_filter = ('completado',)


@admin.register(RegistroTiempo)
class RegistroTiempoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'curso', 'duracion_segundos', 'inicio', 'fin')
    list_filter = ('curso',)
    search_fields = ('usuario__username', 'curso__titulo')
    date_hierarchy = 'inicio'
