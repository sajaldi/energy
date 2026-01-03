from datetime import timedelta
from django.db import models
from django.db.models import Count
from django.contrib import admin, messages
from django.http import HttpResponse
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, DurationWidget
from .models import Categoria, Frecuencia, Rutina, Procedimiento, PasoProcedimiento, Horario, DiaHorario, RestriccionCalendario, Programacion, OrdenTrabajo, Aviso, PlanificacionMensual, CierreOrdenTrabajo
from activos.models import Categoria as CategoriaActivo
from django.utils.safestring import mark_safe
from inventarios.models import MovimientoInventario

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
        fields = ('id', 'nombre', 'padre', 'categoria_activo', 'descripcion')
        export_order = ('id', 'ruta_completa', 'nombre', 'padre', 'categoria_activo', 'descripcion')
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

from django import forms

class SubcategoriaInline(admin.TabularInline):
    model = Categoria
    fk_name = 'padre'
    extra = 1
    verbose_name = "Subcategoría"
    verbose_name_plural = "Subcategorías"
    show_change_link = True
    fields = ('nombre', 'descripcion')
    # Forzar que la descripción sea un input de texto en lugar de un textarea para que quepa en la tabla
    formfield_overrides = {
        models.TextField: {'widget': forms.TextInput(attrs={'style': 'width: 100%; min-width: 400px;'})},
        models.CharField: {'widget': forms.TextInput(attrs={'style': 'width: 100%; min-width: 250px;'})},
    }
    
    class Media:
        css = {
            'all': ('admin/css/forms.css',) # Opcional, pero útil para cargar estilos base
        }

class RutinaInline(admin.TabularInline):
    model = Rutina
    extra = 1
    fields = ('nombre', 'frecuencia', 'tiempo_estimado', 'cantidad_tecnicos', 'procedimiento_estandar')
    readonly_fields = ('nombre',)
    autocomplete_fields = ('frecuencia', 'procedimiento_estandar')
    show_change_link = True
    # classes = ('collapse',)  <-- Eliminado para que aparezca abierto por defecto

@admin.register(Categoria)
class CategoriaAdmin(ImportExportModelAdmin):
    """
    Admin para categorías jerárquicas con estructura simple.
    """
    list_per_page = 50
    resource_class = CategoriaResource
    list_display = ('nombre', 'padre', 'categoria_activo', 'descripcion')
    search_fields = ('nombre',)
    list_filter = ('padre', 'categoria_activo')
    autocomplete_fields = ('padre', 'categoria_activo')
    inlines = [SubcategoriaInline, RutinaInline]


@admin.register(Frecuencia)
class FrecuenciaAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('nombre', 'dias')
    ordering = ('dias',)
    search_fields = ('nombre',)

class RutinaResource(resources.ModelResource):
    """
    Resource personalizado para exportar/importar rutinas.
    
    IMPORTACIÓN: nombre, categoria_nombre, frecuencia_nombre, descripcion, tiempo_estimado, cantidad_tecnicos
    EXPORTACIÓN: Incluye todos los campos con nombres legibles + ruta completa de categoría
    """
    nombre = fields.Field(
        column_name='nombre',
        attribute='nombre'
    )
    
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
    
    procedimiento_estandar = fields.Field(
        column_name='procedimiento_estandar',
        attribute='procedimiento_estandar',
        widget=ForeignKeyWidget(Procedimiento, field='nombre')
    )
    
    tiempo_estimado = fields.Field(
        column_name='tiempo_estimado',
        attribute='tiempo_estimado',
        widget=DurationWidget()
    )
    
    def before_import_row(self, row, **kwargs):
        """Limpia los valores 'None' que el exportador genera como texto"""
        for key in list(row.keys()):
            val = str(row.get(key, '')).strip()
            if val in ['None', 'nan', 'NULL', '']:
                row[key] = None

    class Meta:
        model = Rutina
        import_id_fields = ('id',)
        fields = ('id', 'nombre', 'categoria_nombre', 'categoria_ruta', 
                  'frecuencia_nombre', 'procedimiento_estandar', 'descripcion', 'tiempo_estimado', 'cantidad_tecnicos', 'herramientas')
        export_order = ('id', 'nombre', 'categoria_nombre', 'categoria_ruta', 
                       'frecuencia_nombre', 'procedimiento_estandar', 'tiempo_estimado', 'cantidad_tecnicos', 'herramientas', 'descripcion')
        skip_unchanged = True
        report_skipped = True
        use_bulk = False
    
    def dehydrate_categoria_ruta(self, rutina):
        """Exporta la ruta completa de la categoría"""
        if rutina.categoria:
            return rutina.categoria.get_ruta_completa()
        return ''

class PasoProcedimientoInline(admin.TabularInline):
    model = PasoProcedimiento
    extra = 1

@admin.register(Procedimiento)
class ProcedimientoAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('nombre', 'descripcion', 'creado_en')
    search_fields = ('nombre',)
    inlines = [PasoProcedimientoInline]

class OrdenTrabajoInline(admin.TabularInline):
    model = OrdenTrabajo
    extra = 0
    raw_id_fields = ('rutina', 'aviso', 'tecnico', 'ubicacion')
    fields = ('tipo', 'prioridad', 'rutina', 'ubicacion', 'get_activos_list', 'tecnico', 'inicio_programado', 'estado')
    readonly_fields = ('tipo', 'prioridad', 'rutina', 'ubicacion', 'get_activos_list', 'inicio_programado')
    can_delete = True
    show_change_link = True
    
    def get_activos_list(self, obj):
        # Al usar prefetch_related('activos'), esto no genera queries N+1
        return ", ".join([a.nombre for a in obj.activos.all()])
    get_activos_list.short_description = "Activos"

    def get_queryset(self, request):
        # Optimizamos ubicación profundamente para evitar N+1 en la reconstrucción de la ruta completa
        return super().get_queryset(request).select_related('rutina', 'ubicacion__padre__padre', 'tecnico').prefetch_related('activos')

@admin.register(Rutina)
class RutinaAdmin(ImportExportModelAdmin):
    list_per_page = 50
    resource_class = RutinaResource
    list_display = ('nombre', 'categoria', 'frecuencia', 'tiempo_estimado', 'cantidad_tecnicos')
    list_filter = ('categoria', 'frecuencia')
    search_fields = ('nombre', 'procedimiento_estandar__nombre', 'herramientas')
    autocomplete_fields = ('categoria', 'frecuencia', 'procedimiento_estandar')
    readonly_fields = ('nombre', 'creado_en', 'actualizado_en')
    inlines = [] # Temporalmente vacío hasta que verifiquemos si requiere inlines
    actions = ['exportar_seleccionadas_action']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('categoria', 'frecuencia')
    
    fieldsets = (
        ('Identificación', {
            'fields': ('nombre', 'categoria', 'frecuencia')
        }),
        ('Manual de Pasos', {
            'fields': ('procedimiento_estandar', 'herramientas')
        }),
        ('Detalles de Ejecución', {
            'fields': ('tiempo_estimado', 'cantidad_tecnicos', 'descripcion')
        }),
    )
    
    @admin.action(description="📥 Exportar seleccionadas a Excel")
    def exportar_seleccionadas_action(self, request, queryset):
        """
        Exporta solo las rutinas seleccionadas a un archivo Excel
        utilizando el RutinaResource configurado.
        """
        resource = self.resource_class()
        dataset = resource.export(queryset)
        
        response = HttpResponse(
            dataset.xlsx,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="rutinas_seleccionadas.xlsx"'
        
        self.message_user(
            request,
            f"Se han exportado {queryset.count()} rutinas seleccionadas.",
            messages.SUCCESS
        )
        
        return response


class DiaHorarioInline(admin.TabularInline):
    model = DiaHorario
    extra = 7
    max_num = 7

from django.utils.html import format_html
from django.urls import reverse

@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('nombre', 'descripcion', 'color', 'total_horas_semanales', 'ver_calendario_link')
    search_fields = ('nombre',)
    inlines = [DiaHorarioInline]

    def ver_calendario_link(self, obj):
        url = reverse('mantenimiento:calendario')
        return format_html('<a class="button" href="{}" target="_blank">Ver Programación Anual</a>', url)
    ver_calendario_link.short_description = 'Calendario'


@admin.register(RestriccionCalendario)
class RestriccionCalendarioAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('fecha', 'motivo')
    ordering = ('fecha',)
    search_fields = ('motivo',)


@admin.register(PlanificacionMensual)
class PlanificacionMensualAdmin(admin.ModelAdmin):
    list_per_page = 50
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
    list_per_page = 50
    list_display = ('id', 'rutina', 'get_areas', 'horario', 'procesada', 'ver_cronograma_visual_link')
    list_filter = ('rutina__frecuencia', 'procesada')
    list_select_related = ('rutina', 'horario')
    search_fields = ('id', 'rutina__nombre')
    fields = ('rutina', 'horario', 'areas', 'activos', 'fecha_inicio', 'fecha_fin', 'procesada')
    autocomplete_fields = ('rutina', 'horario', 'areas', 'activos')
    actions = ['generar_ordenes_action', 'reset_procesada_action', 'eliminar_ordenes_action']
    inlines = [OrdenTrabajoInline]

    def ver_calendario_link(self, obj):
        url = reverse('mantenimiento:calendario')
        return format_html('<a class="button" href="{}" target="_blank">Ver Programación Anual</a>', url)
    ver_calendario_link.short_description = 'Calendario'
    
    def ver_cronograma_visual_link(self, obj):
        url = reverse('mantenimiento:cronograma')
        return format_html('<a class="button" href="{}?programacion_id={}" target="_blank" style="background:#3b82f6; color:white;">Ver Cronograma</a>', url, obj.id)
    ver_cronograma_visual_link.short_description = 'Cronograma Visual'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('rutina', 'horario').prefetch_related('areas')

    def get_areas(self, obj):
        # Al usar prefetch_related('areas'), esto no genera queries N+1
        return ", ".join([a.nombre for a in obj.areas.all()])
    get_areas.short_description = 'Áreas'

    @admin.action(description="Generar Órdenes de Trabajo")
    def generar_ordenes_action(self, request, queryset):
        import threading
        from .models import NotificacionMantenimiento
        from django.db import connection

        user_id = request.user.id

        def worker(programacion_id, user_id):
            # En un hilo nuevo, debemos asegurarnos de cerrar la conexión al final
            from django.db import connections
            from .models import Programacion, NotificacionMantenimiento
            try:
                p = Programacion.objects.get(id=programacion_id)
                count = p.generar_ordenes()
                NotificacionMantenimiento.objects.create(
                    user_id=user_id,
                    mensaje=f"Generación completada: Se crearon {count} órdenes para {p.rutina.nombre}.",
                    tipo='SUCCESS'
                )
            except Exception as e:
                NotificacionMantenimiento.objects.create(
                    user_id=user_id,
                    mensaje=f"Error al generar órdenes para {p.rutina.nombre if 'p' in locals() else 'ID '+str(programacion_id)}: {str(e)}",
                    tipo='ERROR'
                )
            finally:
                # Cerrar conexiones en hilos secundarios para evitar fugas
                for conn in connections.all():
                    conn.close()

        for programacion in queryset:
            if programacion.procesada:
                self.message_user(
                    request,
                    f"La programación {programacion.rutina.nombre} ya fue procesada anteriormente.",
                    messages.WARNING
                )
                continue
            
            # Lanzar hilo
            t = threading.Thread(target=worker, args=(programacion.id, user_id))
            t.setDaemon(True)
            t.start()

        self.message_user(
            request, 
            "Iniciando generación en segundo plano para las programaciones seleccionadas. Se te notificará al finalizar.",
            messages.INFO
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
    list_per_page = 50
    list_display = ('id', 'tipo', 'prioridad', 'estado', 'descripcion_corta', 'ubicacion', 'activo', 'solicitante', 'creado_en')
    list_filter = ('tipo', 'estado', 'prioridad', 'creado_en')
    list_select_related = ('ubicacion', 'activo', 'solicitante')
    search_fields = ('descripcion', 'ubicacion__nombre', 'activo__nombre')
    autocomplete_fields = ('activo', 'ubicacion', 'solicitante')
    actions = ['generar_ot_action']
    raw_id_fields = ('activo', 'ubicacion', 'solicitante')

    @admin.display(description='Descripción')
    def descripcion_corta(self, obj):
        if not obj.descripcion: return "-"
        return obj.descripcion[:50] + "..." if len(obj.descripcion) > 50 else obj.descripcion

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
                inicio_programado=aviso.creado_en, 
                fin_programado=aviso.creado_en + timedelta(hours=2),
                notas=aviso.descripcion,
                estado='ESPERA'
            )
            if aviso.activo:
                ot.activos.add(aviso.activo)
            aviso.estado = 'PROCESO'
            aviso.save()
            count += 1
            
        if count:
            self.message_user(request, f"Se han generado {count} Órdenes de Trabajo Correctivas.", messages.SUCCESS)

class CierreOrdenTrabajoInline(admin.StackedInline):
    model = CierreOrdenTrabajo
    extra = 0
    can_delete = False
    verbose_name = "Cierre Técnico de la Orden"
    verbose_name_plural = "Información de Cierre Técnico"
    # Campos organizados de forma premium
    fieldsets = (
        (None, {
            'fields': (('tecnico', 'horas_hombre'), ('fecha_inicio_real', 'fecha_fin_real'), 'comentarios', 'materiales_utilizados')
        }),
    )
    autocomplete_fields = ['tecnico']

class MovimientoInventarioInline(admin.TabularInline):
    model = MovimientoInventario
    extra = 1
    fields = ('material', 'tipo', 'cantidad', 'ubicacion_origen', 'comentarios')
    autocomplete_fields = ['material']
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tipo='SALIDA')

@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('id', 'tipo', 'prioridad', 'get_descripcion', 'ubicacion', 'get_activos_format', 'tecnico', 'estado')
    list_filter = ('tipo', 'prioridad', 'estado', 'inicio_programado', 'tecnico')
    list_select_related = ('rutina', 'aviso', 'tecnico', 'ubicacion', 'programacion')
    search_fields = ('id', 'rutina__nombre', 'aviso__descripcion', 'ubicacion__nombre', 'activos__nombre', 'notas')
    autocomplete_fields = ('rutina', 'aviso', 'tecnico', 'ubicacion', 'programacion')
    date_hierarchy = 'inicio_programado'
    raw_id_fields = ('rutina', 'aviso', 'tecnico', 'ubicacion', 'programacion')
    filter_horizontal = ('activos',)
    inlines = [CierreOrdenTrabajoInline, MovimientoInventarioInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'rutina', 'aviso', 'tecnico', 'ubicacion', 'programacion'
        ).prefetch_related('activos')

    def get_activos_format(self, obj):
        # Usamos .all() que ya está prefetched en el queryset del admin
        activos_list = list(obj.activos.all())
        count = len(activos_list)
        if count == 0: return "-"
        if count == 1: return activos_list[0].nombre
        return f"{count} activos"
    get_activos_format.short_description = 'Activos'

    def get_descripcion(self, obj):
        if obj.rutina:
            return obj.rutina.nombre
        if obj.aviso:
            return f"CORR: {obj.aviso.descripcion[:30]}"
        return "OT Sin descripción"
    get_descripcion.short_description = 'Descripción/Rutina'
