from django.contrib import admin, messages
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, DurationWidget
from mptt.admin import DraggableMPTTAdmin
from mptt.admin import DraggableMPTTAdmin
from .models import Categoria, Frecuencia, Rutina, PasoRutina, Horario, DiaHorario, RestriccionCalendario, Programacion, OrdenTrabajo

class CategoriaResource(resources.ModelResource):
    """
    Resource para import/export de categorías jerárquicas.
    """
    padre_nombre = fields.Field(
        column_name='padre_nombre',
        attribute='padre',
        widget=ForeignKeyWidget(Categoria, field='nombre')
    )
    
    ruta_completa = fields.Field(
        column_name='ruta_completa',
        attribute='ruta_completa',
        readonly=True
    )
    
    clave_unica = fields.Field(
        column_name='clave_unica',
        attribute='get_clave_unica',
        readonly=True
    )
    
    class Meta:
        model = Categoria
        fields = ('id', 'nombre', 'padre_nombre', 'descripcion', 'ruta_completa', 'clave_unica')
        export_order = ('id', 'clave_unica', 'ruta_completa', 'nombre', 'padre_nombre', 'descripcion')
        skip_unchanged = True
        report_skipped = True
    
    def get_instance(self, instance_loader, row):
        """Busca la categoría por nombre + padre"""
        try:
            nombre = row.get('nombre', '').strip()
            padre_nombre = row.get('padre_nombre', '').strip()
            
            if not nombre:
                return None
            
            padre = None
            if padre_nombre:
                try:
                    padre = Categoria.objects.filter(nombre=padre_nombre).first()
                except Categoria.DoesNotExist:
                    return None
            
            if padre:
                return Categoria.objects.filter(nombre=nombre, padre=padre).first()
            else:
                return Categoria.objects.filter(nombre=nombre, padre__isnull=True).first()
                
        except Exception:
            pass
        
        return None

@admin.register(Categoria)
class CategoriaAdmin(ImportExportModelAdmin, DraggableMPTTAdmin):
    """
    Admin para categorías jerárquicas con drag-and-drop.
    """
    resource_class = CategoriaResource
    mptt_indent_field = "nombre"
    list_display = ('tree_actions', 'indented_title', 'descripcion')
    list_display_links = ('indented_title',)
    search_fields = ('nombre',)
    list_filter = ('padre',)


@admin.register(Frecuencia)
class FrecuenciaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'dias')
    ordering = ('dias',)

class RutinaResource(resources.ModelResource):
    """
    Resource personalizado para exportar/importar rutinas.
    
    IMPORTACIÓN: nombre, categoria_nombre, frecuencia_nombre, descripcion, tiempo_estimado, cantidad_tecnicos
    EXPORTACIÓN: Incluye todos los campos con nombres legibles + ruta completa de categoría
    """
    categoria_nombre = fields.Field(
        column_name='categoria_nombre',
        attribute='categoria',
        widget=ForeignKeyWidget(Categoria, field='nombre')
    )
    
    categoria_ruta = fields.Field(
        column_name='categoria_ruta',
        readonly=True
    )
    
    frecuencia_nombre = fields.Field(
        column_name='frecuencia_nombre',
        attribute='frecuencia',
        widget=ForeignKeyWidget(Frecuencia, field='nombre')
    )
    
    class Meta:
        model = Rutina
        fields = ('id', 'nombre', 'categoria_nombre', 'categoria_ruta', 'frecuencia_nombre', 
                  'descripcion', 'tiempo_estimado', 'cantidad_tecnicos')
        export_order = ('id', 'nombre', 'categoria_nombre', 'categoria_ruta', 
                       'frecuencia_nombre', 'tiempo_estimado', 'cantidad_tecnicos', 'descripcion')
        skip_unchanged = True
        report_skipped = True
    
    def dehydrate_categoria_ruta(self, rutina):
        """Exporta la ruta completa de la categoría"""
        if rutina.categoria:
            return rutina.categoria.get_ruta_completa()
        return ''

class PasoRutinaInline(admin.TabularInline):
    model = PasoRutina
    extra = 1

@admin.register(Rutina)
class RutinaAdmin(ImportExportModelAdmin):
    resource_class = RutinaResource
    list_display = ('nombre', 'categoria', 'frecuencia', 'tiempo_estimado', 'cantidad_tecnicos')
    list_filter = ('categoria', 'frecuencia')
    search_fields = ('nombre', 'descripcion')
    inlines = [PasoRutinaInline]


class DiaHorarioInline(admin.TabularInline):
    model = DiaHorario
    extra = 7
    max_num = 7

from django.utils.html import format_html
from django.urls import reverse

@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'total_horas_semanales', 'ver_calendario_link')
    search_fields = ('nombre',)
    inlines = [DiaHorarioInline]

    def ver_calendario_link(self, obj):
        url = reverse('mantenimiento:calendario')
        return format_html('<a class="button" href="{}" target="_blank">Ver Programación Anual</a>', url)
    ver_calendario_link.short_description = 'Calendario'


@admin.register(RestriccionCalendario)
class RestriccionCalendarioAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'motivo')
    ordering = ('fecha',)
    search_fields = ('motivo',)

class OrdenTrabajoInline(admin.TabularInline):
    model = OrdenTrabajo
    extra = 0
    readonly_fields = ('inicio_programado', 'fin_programado', 'estado', 'rutina', 'ubicacion', 'activo')
    can_delete = False

@admin.register(Programacion)
class ProgramacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'rutina', 'get_areas', 'horario', 'procesada')
    list_filter = ('rutina__frecuencia', 'procesada')
    fields = ('rutina', 'horario', 'areas', 'activos', 'fecha_inicio', 'fecha_fin', 'procesada')
    filter_horizontal = ('areas', 'activos')
    actions = ['generar_ordenes_action', 'reset_procesada_action', 'eliminar_ordenes_action']
    inlines = [OrdenTrabajoInline]

    def ver_calendario_link(self, obj):
        url = reverse('mantenimiento:calendario')
        return format_html('<a class="button" href="{}" target="_blank">Ver Programación Anual</a>', url)
    ver_calendario_link.short_description = 'Calendario'

    def get_areas(self, obj):
        return ", ".join([a.nombre for a in obj.areas.all()])
    get_areas.short_description = 'Áreas'

    @admin.action(description="Generar Órdenes de Trabajo")
    def generar_ordenes_action(self, request, queryset):
        for programacion in queryset:
            if programacion.procesada:
                self.message_user(
                    request,
                    f"La programación {programacion.rutina.nombre} ya fue procesada anteriormente.",
                    messages.WARNING
                )
                continue
                
            count = programacion.generar_ordenes()
            self.message_user(
                request, 
                f"Se han generado/verificado {count} órdenes para {programacion.rutina.nombre} ({programacion.areas.count()} áreas/hijos).",
                messages.SUCCESS
            )

    @admin.action(description="Resetear estado (Permitir re-generar)")
    def reset_procesada_action(self, request, queryset):
        rows_updated = queryset.update(procesada=False)
        self.message_user(request, f"{rows_updated} programaciones han sido reseteadas.", messages.SUCCESS)

    @admin.action(description="ELIMINAR órdenes generadas")
    def eliminar_ordenes_action(self, request, queryset):
        for programacion in queryset:
            count = programacion.ordenes.count()
            programacion.ordenes.all().delete()
            programacion.procesada = False
            programacion.save()
            self.message_user(
                request, 
                f"Se han eliminado {count} órdenes de {programacion.rutina.nombre} y se ha reseteado su estado.",
                messages.SUCCESS
            )



@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_display = ('id', 'rutina', 'ubicacion', 'activo', 'inicio_programado', 'fin_programado', 'estado')
    list_filter = ('estado', 'inicio_programado', 'rutina', 'ubicacion')
    search_fields = ('rutina__nombre', 'ubicacion__nombre', 'activo__nombre', 'notas')
    date_hierarchy = 'inicio_programado'
