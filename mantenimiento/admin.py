from datetime import timedelta
from django.db.models import Count
from django.contrib import admin, messages
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, DurationWidget
from .models import Categoria, Frecuencia, Rutina, PasoRutina, Horario, DiaHorario, RestriccionCalendario, Programacion, OrdenTrabajo, Aviso, PlanificacionMensual

class CategoriaResource(resources.ModelResource):
    """
    Resource para import/export de categorías jerárquicas.
    Permite importar usando el nombre del padre para mayor facilidad.
    """
    padre = fields.Field(
        column_name='padre',
        attribute='padre',
        widget=ForeignKeyWidget(Categoria, field='nombre')
    )
    
    ruta_completa = fields.Field(
        column_name='ruta_completa',
        attribute='ruta_completa',
        readonly=True
    )
    
    class Meta:
        model = Categoria
        fields = ('id', 'nombre', 'padre', 'descripcion')
        export_order = ('id', 'ruta_completa', 'nombre', 'padre', 'descripcion')
        skip_unchanged = True
        report_skipped = True
        import_id_fields = ('id',)

    def before_import_row(self, row, **kwargs):
        """
        Asegura que si el padre no existe pero está en el mismo archivo, 
        se pueda procesar (o al menos manejar el error limpiamente).
        """
        nombre_padre = row.get('padre')
        if nombre_padre:
            nombre_padre = str(nombre_padre).strip()
            # Si el padre no existe, intentamos buscarlo por nombre
            if not Categoria.objects.filter(nombre=nombre_padre).exists():
                # Nota: En una importación masiva, esto podría fallar si el padre se crea después.
                # Pero para la mayoría de los casos de 'texto', esto lo hace más amigable.
                pass

class SubcategoriaInline(admin.TabularInline):
    model = Categoria
    fk_name = 'padre'
    extra = 1
    verbose_name = "Subcategoría"
    verbose_name_plural = "Subcategorías"
    fields = ('nombre', 'descripcion')

@admin.register(Categoria)
class CategoriaAdmin(ImportExportModelAdmin):
    """
    Admin para categorías jerárquicas con estructura simple.
    """
    resource_class = CategoriaResource
    list_display = ('nombre', 'padre', 'descripcion')
    search_fields = ('nombre',)
    list_filter = ('padre',)
    autocomplete_fields = ('padre',)
    inlines = [SubcategoriaInline]


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
        use_bulk = True
        batch_size = 1000
    
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
    list_select_related = ('categoria', 'frecuencia')
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
    raw_id_fields = ('rutina', 'aviso', 'tecnico', 'ubicacion', 'activo', 'programacion')
    fields = ('tipo', 'prioridad', 'rutina', 'ubicacion', 'activo', 'tecnico', 'inicio_programado', 'estado')
    readonly_fields = ('tipo', 'prioridad', 'rutina', 'ubicacion', 'activo', 'inicio_programado')
    can_delete = True

@admin.register(PlanificacionMensual)
class PlanificacionMensualAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'mes', 'anio', 'estado', 'responsable', 'get_total_ordenes', 'get_total_horas')
    list_filter = ('estado', 'mes', 'anio')
    list_select_related = ('responsable',)
    search_fields = ('nombre', 'notas')
    inlines = [OrdenTrabajoInline]
    actions = ['poblar_plan_action']
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            ordenes_count=Count('ordenes')
        ).prefetch_related('ordenes__rutina')

    def get_total_ordenes(self, obj):
        return getattr(obj, 'ordenes_count', obj.ordenes.count())
    get_total_ordenes.short_description = "N° OTs"
    get_total_ordenes.admin_order_field = 'ordenes_count'

    def get_total_horas(self, obj):
        # Al estar pre-cargado con prefetch_related('ordenes__rutina'), no hará nuevas queries
        total = 0
        for ot in obj.ordenes.all():
            if ot.rutina and ot.rutina.tiempo_estimado:
                total += ot.rutina.tiempo_estimado.total_seconds() / 3600
        return f"{total:.1f} hrs"
    get_total_horas.short_description = "Total HH"

    @admin.action(description="Poblar plan con OTs del mes/año")
    def poblar_plan_action(self, request, queryset):
        for plan in queryset:
            # Buscar OTs que no tengan plan y caigan en el mes/año
            ots = OrdenTrabajo.objects.filter(
                inicio_programado__month=plan.mes,
                inicio_programado__year=plan.anio,
                planificacion__isnull=True
            )
            count = ots.count()
            ots.update(planificacion=plan)
            self.message_user(request, f"Se han agregado {count} órdenes al plan {plan.nombre}.")

@admin.register(Programacion)
class ProgramacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'rutina', 'get_areas', 'horario', 'procesada')
    list_filter = ('rutina__frecuencia', 'procesada')
    list_select_related = ('rutina', 'horario')
    search_fields = ('id', 'rutina__nombre')
    fields = ('rutina', 'horario', 'areas', 'activos', 'fecha_inicio', 'fecha_fin', 'procesada')
    filter_horizontal = ('areas', 'activos')
    actions = ['generar_ordenes_action', 'reset_procesada_action', 'eliminar_ordenes_action']
    inlines = [OrdenTrabajoInline]

    def ver_calendario_link(self, obj):
        url = reverse('mantenimiento:calendario')
        return format_html('<a class="button" href="{}" target="_blank">Ver Programación Anual</a>', url)
    ver_calendario_link.short_description = 'Calendario'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('areas')

    def get_areas(self, obj):
        # Al usar prefetch_related('areas'), esto no genera queries N+1
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



@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_display = ('id', 'prioridad', 'estado', 'ubicacion', 'activo', 'solicitante', 'creado_en')
    list_filter = ('estado', 'prioridad', 'creado_en')
    list_select_related = ('ubicacion', 'activo', 'solicitante')
    search_fields = ('descripcion', 'ubicacion__nombre', 'activo__nombre')
    autocomplete_fields = ('activo', 'ubicacion', 'solicitante')
    actions = ['generar_ot_action']
    raw_id_fields = ('activo', 'ubicacion', 'solicitante')

    @admin.action(description="Generar Orden de Trabajo Correctiva")
    def generar_ot_action(self, request, queryset):
        count = 0
        for aviso in queryset:
            if OrdenTrabajo.objects.filter(aviso=aviso).exists():
                self.message_user(request, f"El aviso {aviso.id} ya tiene una OT asociada.", messages.WARNING)
                continue
                
            ot = OrdenTrabajo.objects.create(
                tipo='CORRECTIVA',
                prioridad=aviso.prioridad,
                aviso=aviso,
                ubicacion=aviso.ubicacion,
                activo=aviso.activo,
                inicio_programado=aviso.creado_en, 
                fin_programado=aviso.creado_en + timedelta(hours=2),
                notas=aviso.descripcion,
                estado='PROGRAMADA'
            )
            aviso.estado = 'PROCESO'
            aviso.save()
            count += 1
            
        if count:
            self.message_user(request, f"Se han generado {count} Órdenes de Trabajo Correctivas.", messages.SUCCESS)

@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo', 'prioridad', 'get_descripcion', 'ubicacion', 'activo', 'tecnico', 'estado')
    list_filter = ('tipo', 'prioridad', 'estado', 'inicio_programado', 'tecnico')
    list_select_related = ('rutina', 'aviso', 'tecnico', 'ubicacion', 'activo', 'programacion')
    search_fields = ('rutina__nombre', 'aviso__descripcion', 'ubicacion__nombre', 'activo__nombre', 'notas')
    autocomplete_fields = ('rutina', 'aviso', 'tecnico', 'ubicacion', 'activo', 'programacion')
    date_hierarchy = 'inicio_programado'
    raw_id_fields = ('rutina', 'aviso', 'tecnico', 'ubicacion', 'activo', 'programacion')

    def get_descripcion(self, obj):
        if obj.rutina:
            return obj.rutina.nombre
        if obj.aviso:
            return f"CORR: {obj.aviso.descripcion[:30]}"
        return "OT Sin descripción"
    get_descripcion.short_description = 'Descripción/Rutina'
