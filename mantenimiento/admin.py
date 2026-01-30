from datetime import datetime, timedelta
import time
import os
import sys
from django.db import models
from django.db.models import Count
from django.contrib import admin, messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, DurationWidget
from .models import Categoria, Frecuencia, Rutina, Procedimiento, PasoProcedimiento, Horario, DiaHorario, RestriccionCalendario, Programacion, OrdenTrabajo, Aviso, PlanificacionMensual, CierreOrdenTrabajo, PuestoTrabajo, TecnicoPuesto, ValorPasoOrden, Falla, FotoAviso
from activos.models import Categoria as CategoriaActivo
from django.utils.safestring import mark_safe
from django.urls import reverse, path
from django.contrib.auth.models import User
from inventarios.models import MovimientoInventario
import datetime as dt_python
from import_export.widgets import ForeignKeyWidget, DurationWidget, ManyToManyWidget, DateTimeWidget
from activos.models import Activo, Ubicacion
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

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

@admin.register(PuestoTrabajo)
class PuestoTrabajoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'ver_dashboard_link')
    search_fields = ('nombre',)

    def ver_dashboard_link(self, obj):
        url = reverse('mantenimiento:dashboard_cargas')
        return mark_safe(f'<a class="button" href="{url}" style="background: #4f46e5; color: white; font-weight: 700;">📊 VER DASHBOARD DE CARGAS</a>')
    ver_dashboard_link.short_description = 'Dashboard'

@admin.register(TecnicoPuesto)
class TecnicoPuestoAdmin(admin.ModelAdmin):
    list_display = ('user', 'puesto', 'get_carga_semanal', 'disponible', 'horas_semanales_max')
    list_filter = ('puesto', 'disponible')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'puesto__nombre')
    autocomplete_fields = ('user', 'puesto')

    def get_carga_semanal(self, obj):
        from .models import OrdenTrabajo
        from django.utils import timezone
        
        now = timezone.now()
        monday = now - timedelta(days=now.weekday())
        sunday = monday + timedelta(days=6)
        
        # Convertir fechas a datetimes conscientes
        q_start = timezone.make_aware(datetime.combine(monday, datetime.min.time()))
        q_end = timezone.make_aware(datetime.combine(sunday, datetime.max.time()))
        
        ots = OrdenTrabajo.objects.filter(
            tecnico=obj.user,
            inicio_programado__gte=q_start,
            inicio_programado__lte=q_end
        )
        
        total_horas = 0
        for ot in ots:
            if ot.inicio_programado and ot.fin_programado:
                total_horas += (ot.fin_programado - ot.inicio_programado).total_seconds() / 3600
        
        pct = (total_horas / float(obj.horas_semanales_max) * 100) if obj.horas_semanales_max > 0 else 0
        
        color = '#10b981' # Success green
        if pct > 100: color = '#ef4444' # Danger red
        elif pct > 80: color = '#f59e0b' # Warning orange
        
        return mark_safe(f'<b style="color: {color}; font-size: 13px;">{pct:.1f}%</b> <small style="color: #64748b;">({total_horas:.1f}h / {obj.horas_semanales_max}h)</small>')
    get_carga_semanal.short_description = 'Carga esta Semana'

class FlexibleDurationWidget(DurationWidget):
    """
    Widget de duración ultra-flexible que soporta:
    - Formatos HH:MM (ej: 08:00 -> 8 horas)
    - Objetos datetime.time de Excel
    - Números decimales (ej: 1.5 -> 1.5 horas)
    - Formato estándar de Django (D HH:MM:SS)
    """
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        
        # 1. Si ya es un objeto timedelta o similar, dejarlo pasar
        if isinstance(value, dt_python.timedelta):
            return value
            
        # 2. Si es un objeto time de Python (común en imports de Excel/tablib)
        if isinstance(value, dt_python.time):
            return dt_python.timedelta(hours=value.hour, minutes=value.minute, seconds=value.second)

        val_str = str(value).strip()
        
        # 3. Caso HH:MM (muy común en Excel)
        if ":" in val_str and val_str.count(":") == 1:
            try:
                h, m = val_str.split(":")
                return dt_python.timedelta(hours=int(h), minutes=int(m))
            except (ValueError, TypeError):
                pass
        
        # 4. Caso HH:MM:SS
        if ":" in val_str and val_str.count(":") == 2:
            try:
                h, m, s = val_str.split(":")
                return dt_python.timedelta(hours=int(h), minutes=int(m), seconds=int(s))
            except (ValueError, TypeError):
                pass

        # 5. Caso número decimal (asumimos que son HORAS)
        try:
            return dt_python.timedelta(hours=float(val_str))
        except (ValueError, TypeError):
            pass

        # Fallback al widget original de import-export
        return super().clean(value, row, *args, **kwargs)

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
    
    codigo_rutina = fields.Field(
        column_name='codigo_rutina',
        attribute='codigo_rutina'
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
        widget=FlexibleDurationWidget()
    )
    
    def skip_row(self, instance, original, row, import_validation_errors=None, **kwargs):
        """
        Omitir el registro si no tiene código de rutina.
        """
        codigo = row.get('codigo_rutina')
        if not codigo or str(codigo).strip() in ['None', 'nan', 'NULL', '']:
            return True
        return super().skip_row(instance, original, row, import_validation_errors, **kwargs)

    def before_import_row(self, row, **kwargs):
        """Limpia los valores 'None' y quita espacios de los campos clave"""
        for key in list(row.keys()):
            val = row.get(key)
            if val is None:
                continue
            
            val_str = str(val).strip()
            # Limpiar nulos de Excel/CSV
            if val_str.lower() in ['none', 'nan', 'null', '']:
                row[key] = None
            else:
                # Quitar espacios al inicio y final de los strings
                if isinstance(val, str):
                    row[key] = val.strip()
                else:
                    row[key] = val_str

    class Meta:
        model = Rutina
        import_id_fields = ('codigo_rutina',) # Usar el código como identificador único para el importador
        fields = ('id', 'codigo_rutina', 'nombre', 'categoria_nombre', 'categoria_ruta', 
                  'frecuencia_nombre', 'procedimiento_estandar', 'descripcion', 'tiempo_estimado', 'cantidad_tecnicos', 'herramientas')
        export_order = ('id', 'codigo_rutina', 'nombre', 'categoria_nombre', 'categoria_ruta', 
                       'frecuencia_nombre', 'procedimiento_estandar', 'tiempo_estimado', 'cantidad_tecnicos', 'herramientas', 'descripcion')
        skip_unchanged = True
        report_skipped = True
        use_bulk = False
    
    def dehydrate_categoria_ruta(self, rutina):
        """Exporta la ruta completa de la categoría"""
        if rutina.categoria:
            return rutina.categoria.get_ruta_completa()
        return ''

class ManyToManyCodeWidget(ManyToManyWidget):
    """
    Widget para ManyToMany que usa codigo_interno en lugar de ID.
    Soporta múltiples códigos separados por coma.
    """
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return self.model.objects.none()
        
        codes = [c.strip() for c in str(value).split(',') if c.strip()]
        return self.model.objects.filter(codigo_interno__in=codes)

    def render(self, value, obj=None):
        if not value:
            return ""
        return ", ".join([str(obj.codigo_interno) for obj in value.all()])

class SmartHierarchicalWidget(ForeignKeyWidget):
    """
    Widget inteligente que resuelve ubicaciones jerárquicas desambiguando por el padre.
    Soporta formatos: "Padre -> Hijo", "Padre | Hijo", "Padre - Hijo".
    """
    def clean(self, value, row=None, *args, **kwargs):
        val_str = str(value).strip()
        if not val_str:
            return None
            
        import re
        # Dividir por separadores comunes
        parts = [p.strip() for p in re.split(r'\s*(?:->|\||-)\s*', val_str) if p.strip()]
        
        if not parts:
            return None
            
        leaf_name = parts[-1]
        
        # 1. Búsqueda por nombre exacto (case-insensitive)
        candidates = self.model.objects.filter(nombre__iexact=leaf_name)
        
        count = candidates.count()
        if count == 0:
            raise ValueError(f"No existe ubicación con nombre '{leaf_name}'")
            
        if count == 1:
            return candidates.first()
            
        # 2. Desambiguación usando el padre inmediato (si existe en el string)
        if len(parts) > 1:
            parent_name = parts[-2]
            # Filtrar aquellos candidatos cuyo padre llame igual
            filtered = candidates.filter(padre__nombre__iexact=parent_name)
            
            if filtered.count() == 1:
                return filtered.first()
                
            if filtered.count() > 1:
                raise ValueError(f"Ambigüedad persistente: {filtered.count()} ubicaciones '{leaf_name}' tienen padre '{parent_name}'.")
                
            # Si no coincide el padre directo, reportar error claro
            raise ValueError(f"Conflicto: Se encontró '{leaf_name}' pero ninguno pertenece a '{parent_name}'.")
            
        # Si hay duplicados y no se dio contexto de padre
        names = [f"{c.nombre} (Padre: {c.padre})" for c in candidates[:3]]
        raise ValueError(f"Ambigüedad: '{leaf_name}' existe {count} veces. Usa formato 'Padre -> Hijo'. Ejemplos: {', '.join(names)}...")

class OrdenTrabajoResource(resources.ModelResource):
    rutina_codigo = fields.Field(
        column_name='rutina_codigo',
        attribute='rutina',
        widget=ForeignKeyWidget(Rutina, field='codigo_rutina')
    )
    ubicacion_nombre = fields.Field(
        column_name='ubicacion_nombre',
        attribute='ubicacion',
        widget=SmartHierarchicalWidget(Ubicacion, field='nombre')
    )
    tecnico_usuario = fields.Field(
        column_name='tecnico_usuario',
        attribute='tecnico',
        widget=ForeignKeyWidget(User, field='username')
    )
    activos_codigos = fields.Field(
        column_name='activos_codigos',
        attribute='activos',
        widget=ManyToManyCodeWidget(Activo, field='codigo_interno')
    )
    
    inicio_programado = fields.Field(
        column_name='inicio_programado',
        attribute='inicio_programado',
        widget=DateTimeWidget(format='%Y-%m-%d %H:%M:%S')
    )
    fin_programado = fields.Field(
        column_name='fin_programado',
        attribute='fin_programado',
        widget=DateTimeWidget(format='%Y-%m-%d %H:%M:%S')
    )

    class Meta:
        model = OrdenTrabajo
        import_id_fields = ('id',)
        fields = ('id', 'tipo', 'prioridad', 'rutina_codigo', 'ubicacion_nombre', 
                  'tecnico_usuario', 'activos_codigos', 'inicio_programado', 'fin_programado', 
                  'estado', 'notas')
        export_order = fields

    def before_import_row(self, row, **kwargs):
        """Limpieza de datos similar a RutinaResource"""
        for key in list(row.keys()):
            val = str(row.get(key, '')).strip()
            if val in ['None', 'nan', 'NULL', '']:
                row[key] = None

        # Fix de ubicaciones removido: lo maneja SmartHierarchicalWidget para evitar ambigüedades.

        # Calculo automático de fin_programado si falta
        inicio_str = row.get('inicio_programado')
        fin_str = row.get('fin_programado')
        rutina_code = row.get('rutina_codigo')

        if inicio_str and not fin_str and rutina_code:
            try:
                from datetime import datetime, timedelta
                # Intentar parsear inicio (asumimos formato Excel/CSV común)
                # Ojo: esto depende del LC_TIME o settings, pero probaremos formatos estándar
                formats = ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M:%S']
                inicio_dt = None
                for fmt in formats:
                    try:
                        inicio_dt = datetime.strptime(str(inicio_str).strip(), fmt)
                        break
                    except ValueError: continue
                
                if inicio_dt:
                    rutina = Rutina.objects.filter(codigo_rutina=rutina_code).first()
                    if rutina:
                        duration = rutina.tiempo_estimado or timedelta(hours=1)
                        fin_dt = inicio_dt + duration
                        row['fin_programado'] = fin_dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                # Si falla el cálculo, dejamos que falle la validación normal o siga null
                pass

class PasoProcedimientoInline(admin.TabularInline):
    model = PasoProcedimiento
    extra = 1
    fields = ('orden', 'descripcion', 'tipo_respuesta', 'unidad_medida', 'valor_objetivo', 'rango_min', 'rango_max', 'punto_medicion_exacto', 'punto_medicion_codigo')

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
    fields = ('tipo', 'prioridad', 'rutina', 'ubicacion', 'get_activos_list', 'tecnico', 'equipo', 'inicio_programado', 'estado')
    readonly_fields = ('tipo', 'prioridad', 'rutina', 'ubicacion', 'get_activos_list', 'inicio_programado')
    can_delete = True
    show_change_link = True
    
    def get_activos_list(self, obj):
        # Al usar prefetch_related('activos'), esto no genera queries N+1
        return ", ".join([a.nombre for a in obj.activos.all()])
    get_activos_list.short_description = "Activos"

    def get_queryset(self, request):
        # Optimizamos ubicación profundamente para evitar N+1 en la reconstrucción de la ruta completa
        return super().get_queryset(request).select_related('rutina', 'ubicacion__padre__padre', 'tecnico', 'equipo').prefetch_related('activos')

class ProgramacionInline(admin.TabularInline):
    model = Programacion
    extra = 0
    readonly_fields = ('creado_en', 'horario', 'fecha_inicio', 'fecha_fin', 'procesada', 'ver_detalle_link')
    fields = ('creado_en', 'horario', 'fecha_inicio', 'fecha_fin', 'procesada', 'ver_detalle_link')
    ordering = ('-creado_en',)
    can_delete = False
    show_change_link = True
    
    def ver_detalle_link(self, obj):
        if obj.id:
            url = reverse('admin:mantenimiento_programacion_change', args=[obj.id])
            return mark_safe(f'<a href="{url}">🔍 Ver Detalle</a>')
        return "-"
    ver_detalle_link.short_description = 'Acciones'

@admin.register(Rutina)
class RutinaAdmin(ImportExportModelAdmin):
    change_list_template = 'admin/mantenimiento/rutina/change_list.html'
    list_per_page = 50
    resource_class = RutinaResource
    list_display = ('codigo_rutina', 'nombre', 'categoria', 'frecuencia', 'puesto_trabajo', 'tiempo_estimado', 'cantidad_tecnicos', 'programar_rutina_link')
    list_filter = (('categoria', admin.RelatedOnlyFieldListFilter), 'frecuencia', 'puesto_trabajo')
    search_fields = ('codigo_rutina', 'nombre', 'procedimiento_estandar__nombre', 'herramientas')
    autocomplete_fields = ('categoria', 'frecuencia', 'procedimiento_estandar', 'puesto_trabajo')
    readonly_fields = ('creado_en', 'actualizado_en', 'programar_rutina_link')
    list_select_related = True
    inlines = [ProgramacionInline] # Agregado historial de programaciones
    actions = ['exportar_seleccionadas_action']

    def programar_rutina_link(self, obj):
        if not obj.id: return "-"
        url = reverse('mantenimiento:programar_rutina_wizard') + f'?rutina={obj.id}'
        return mark_safe(f'<a class="button" href="{url}" style="background: #10b981; color: white; font-weight: 700; padding: 5px 15px; border-radius: 4px; text-decoration: none;">🗓️ PROGRAMAR ESTA RUTINA</a>')
    programar_rutina_link.short_description = 'Programación'

    def get_queryset(self, request):
        # Optimización profunda para evitar N+1 en la renderización de la ruta de categorías (soporta hasta 6 niveles)
        return super().get_queryset(request).select_related(
            'categoria__padre__padre__padre__padre__padre', 
            'frecuencia', 
            'puesto_trabajo'
        )
    
    fieldsets = (
        ('Identificación', {
            'fields': ('codigo_rutina', ('nombre', 'programar_rutina_link'), 'categoria', 'frecuencia', 'puesto_trabajo')
        }),
        ('Manual de Pasos', {
            'fields': ('procedimiento_estandar', 'herramientas')
        }),
        ('Detalles de Ejecución', {
            'fields': ('tiempo_estimado', 'cantidad_tecnicos', 'descripcion')
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        from .views import import_rutinas
        custom_urls = [
            path('import-background/', self.admin_site.admin_view(import_rutinas.import_rutinas_background), name='mantenimiento_rutina_import_background'),
            path('import-background/process/', csrf_exempt(self.admin_site.admin_view(import_rutinas.import_rutinas_process)), name='mantenimiento_rutina_import_process'),
            path('import-background/progress/', self.admin_site.admin_view(import_rutinas.import_rutinas_progress), name='mantenimiento_rutina_import_progress'),
            path('import-background/template/', self.admin_site.admin_view(self.download_template_view), name='mantenimiento_rutina_import_template'),
        ]
        return custom_urls + urls

    def download_template_view(self, request):
        """Genera un archivo Excel vacío con las cabeceras del recurso de Rutinas"""
        dataset = RutinaResource().export(queryset=Rutina.objects.none())
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="formato_importacion_rutinas.xlsx"'
        return response

    
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
            
            if programacion.fecha_inicio.year < 2000:
                self.message_user(
                    request,
                    f"La programación {programacion.id} tiene una fecha de inicio inválida ({programacion.fecha_inicio}). Por favor corrígala.",
                    messages.ERROR
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



class FallaInline(admin.TabularInline):
    model = Falla
    extra = 1
    fk_name = 'padre'
    fields = ('nombre', 'descripcion')
    verbose_name = "Sub-falla / Síntoma"
    verbose_name_plural = "Sub-fallas (Hijos)"

@admin.register(Falla)
class FallaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'padre', 'puesto_trabajo', 'get_ruta_completa')
    list_filter = ('padre', 'puesto_trabajo')
    search_fields = ('nombre',)
    raw_id_fields = ('padre', 'puesto_trabajo')
    inlines = [FallaInline]

    def get_ruta_completa(self, obj):
        return obj.get_ruta_completa()
    get_ruta_completa.short_description = 'Ruta Completa'

class FotoAvisoInline(admin.TabularInline):
    model = FotoAviso
    extra = 1

# Importar inline de Mayan
from documentos.admin_mayan import MayanDocumentInline

@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('id', 'tipo', 'prioridad', 'estado', 'falla', 'descripcion_corta', 'ubicacion', 'activo', 'solicitante', 'creado_en')
    list_filter = ('tipo', 'estado', 'prioridad', 'falla', 'creado_en')
    list_select_related = ('ubicacion', 'activo', 'solicitante', 'falla')
    search_fields = ('descripcion', 'ubicacion__nombre', 'activo__nombre')
    autocomplete_fields = ('activo', 'ubicacion', 'solicitante', 'falla')
    actions = ['generar_ot_action']
    raw_id_fields = ('activo', 'ubicacion', 'solicitante', 'falla')
    inlines = [FotoAvisoInline, MayanDocumentInline]

    def add_view(self, request, form_url='', extra_context=None):
        """Redirigir a la interfaz móvil renovada"""
        from django.shortcuts import redirect
        if request.GET.get('mode') != 'admin':
            return redirect('mantenimiento:mobile_crear_aviso')
        return super().add_view(request, form_url, extra_context)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "falla":
            puesto_tecnico = getattr(request.user, 'perfil_tecnico', None)
            if puesto_tecnico and not request.user.is_superuser:
                # Filtrar fallas que cuelgan de raíces del puesto
                roots = Falla.objects.filter(puesto_trabajo=puesto_tecnico.puesto)
                ids = []
                for r in roots:
                    def get_ids(n):
                        ids.append(n.id)
                        for h in n.hijos.all(): get_ids(h)
                    get_ids(r)
                kwargs["queryset"] = Falla.objects.filter(id__in=ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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
                falla=aviso.falla,
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

class PermisosTrabajoInline(admin.TabularInline):
    from seguridad.models import PermisoTrabajo
    model = PermisoTrabajo
    extra = 0
    can_delete = False
    fields = ('tipo', 'estado', 'solicitante', 'fecha_inicio', 'ver_permiso_link')
    readonly_fields = ('tipo', 'estado', 'solicitante', 'fecha_inicio', 'ver_permiso_link')
    verbose_name = "Permiso de Trabajo Vinculado"
    verbose_name_plural = "Permisos de Trabajo"
    
    def ver_permiso_link(self, obj):
        if obj.id:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('seguridad:detalle_permiso', args=[obj.id])
            return format_html('<a href="{}" class="button" style="background-color: #8b5cf6; color: white; padding: 3px 8px; border-radius: 4px;" target="_blank">Ver Permiso</a>', url)
        return "-"
    ver_permiso_link.short_description = "Acciones"


class ValorPasoOrdenInline(admin.TabularInline):
    model = ValorPasoOrden
    extra = 0
    raw_id_fields = ('paso', 'capturado_por')
    fields = ('paso', 'valor_texto', 'valor_numerico', 'valor_bool', 'no_aplica', 'comentarios')
    readonly_fields = ('paso', 'capturado_por', 'creado_en')

# ... imports al inicio del archivo o aqui mismo ...
from documentos.admin_mayan import MayanDocumentInline

@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = ('id', 'tipo', 'prioridad', 'get_descripcion', 'get_ubicacion_jerarquia', 'get_activos_format', 'tecnico', 'equipo', 'estado', 'registrar_salida_link', 'generar_permiso_action')
    list_filter = ('tipo', 'prioridad', 'estado', 'inicio_programado', 'tecnico', 'equipo')
    readonly_fields = ('registrar_salida_link',)
    list_select_related = ('rutina', 'aviso', 'tecnico', 'equipo', 'ubicacion', 'programacion')
    search_fields = ('id', 'rutina__nombre', 'aviso__descripcion', 'ubicacion__nombre', 'activos__nombre', 'notas')
    autocomplete_fields = ('rutina', 'aviso', 'tecnico', 'equipo', 'ubicacion', 'programacion', 'activos')
    ordering = ('-id',)
    date_hierarchy = 'inicio_programado'
    raw_id_fields = ('rutina', 'aviso', 'tecnico', 'ubicacion', 'programacion')
    # filter_horizontal = ('activos',)
    inlines = [CierreOrdenTrabajoInline, MovimientoInventarioInline, PermisosTrabajoInline, ValorPasoOrdenInline, MayanDocumentInline]


    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'rutina', 'aviso', 'tecnico', 'equipo', 'ubicacion', 'programacion'
        ).prefetch_related('activos')

    def get_activos_format(self, obj):
        # Usamos .all() que ya está prefetched en el queryset del admin
        activos_list = list(obj.activos.all())
        count = len(activos_list)
        if count == 0: return "-"
        if count == 1: return activos_list[0].nombre
        return f"{count} activos"
    get_activos_format.short_description = 'Activos'

    def get_ubicacion_jerarquia(self, obj):
        if obj.ubicacion:
            return obj.ubicacion.get_ruta_completa()
        return "-"
    get_ubicacion_jerarquia.short_description = 'Ubicación'
    get_ubicacion_jerarquia.admin_order_field = 'ubicacion__nombre'

    def get_descripcion(self, obj):
        if obj.rutina:
            return obj.rutina.nombre
        if obj.aviso:
            return f"CORR: {obj.aviso.descripcion[:30]}"
        return "OT Sin descripción"
    get_descripcion.short_description = 'Descripción/Rutina'

    def registrar_salida_link(self, obj):
        if obj.estado in ['PROGRAMADA', 'EJECUCION']:
            try:
                url = reverse('inventarios:registrar_salida')
                return mark_safe(f'<a class="button" href="{url}?ot={obj.id}" style="background: #6366f1; color: white; padding: 4px 10px; border-radius: 4px; font-weight: 600; text-decoration: none;">📦 Salida de Material</a>')
            except Exception:
                # Fallback en caso de error de reversión (ej. migraciones o urls no cargadas)
                return "-"
        return "-"
    registrar_salida_link.short_description = "Acciones"

    def generar_permiso_action(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        if obj.permisos.exists():
            permiso = obj.permisos.first()
            url = reverse('seguridad:detalle_permiso', args=[permiso.id])
            return format_html('<a href="{}" class="button" style="background-color: #059669; color: white; padding: 3px 8px; border-radius: 4px;">Ver Permiso</a>', url)
        
        url = reverse('seguridad:generar_permiso_ot', args=[obj.id])
        return format_html('<a href="{}" class="button" style="background-color: #2563eb; color: white; padding: 3px 8px; border-radius: 4px;">Generar Permiso</a>', url)
    
    generar_permiso_action.short_description = "Permiso de Trabajo"
    generar_permiso_action.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-background/', self.admin_site.admin_view(self.import_background_view), name='mantenimiento_ordentrabajo_import_background'),
            path('import-background/process/', csrf_exempt(self.admin_site.admin_view(self.import_process_view)), name='mantenimiento_ordentrabajo_import_process'),
            path('import-background/progress/', self.admin_site.admin_view(self.import_progress_api), name='mantenimiento_ordentrabajo_import_progress'),
            path('import-background/template/', self.admin_site.admin_view(self.download_template_view), name='mantenimiento_ordentrabajo_import_template'),
            path('test-connectivity/', self.admin_site.admin_view(self.test_connectivity), name='mantenimiento_ordentrabajo_test_connectivity'),
            path('pure-ping/', self.admin_site.admin_view(self.pure_ping), name='mantenimiento_ordentrabajo_pure_ping'),
        ]
        return custom_urls + urls

    def download_template_view(self, request):
        """Genera un archivo Excel vacío con las cabeceras del recurso"""
        dataset = OrdenTrabajoResource().export(queryset=OrdenTrabajo.objects.none())
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="formato_importacion_ots.xlsx"'
        return response

    def import_background_view(self, request):
        """Vista para subir el archivo de importación"""
        opts = self.model._meta
        context = {
            **self.admin_site.each_context(request),
            'title': f'Importación Aislada de {opts.verbose_name_plural}',
            'opts': opts,
            'app_label': opts.app_label,
        }
        return render(request, 'admin/mantenimiento/ordentrabajo/import_background.html', context)

    def import_process_view(self, request):
        """Inicia la tarea de Celery"""
        start_time = time.time()
        print(f"[DEBUG] Inicio import_process_view a las {time.ctime()}")
        sys.stdout.flush()

        if request.method == 'POST' and request.FILES.get('file'):
            import_file = request.FILES['file']
            print(f"[DEBUG] Archivo: {import_file.name} | Tamaño: {import_file.size} bytes")
            sys.stdout.flush()
            
            from django.core.files.storage import default_storage
            from django.core.cache import cache

            # 1. Probar conexion a Cache/Redis antes de nada
            try:
                print("[DEBUG] Probando conexion a Redis/Cache...")
                sys.stdout.flush()
                cache.set('test_conn', 'ok', 5)
                if cache.get('test_conn') == 'ok':
                    print("[DEBUG] Conexion a Redis exitosa.")
                else:
                    print("[DEBUG] Redis no guardo el valor de prueba.")
                sys.stdout.flush()
            except Exception as e:
                print(f"[DEBUG] Error de conexion a Redis: {str(e)}")
                sys.stdout.flush()

            filename = f"imports/ots_{request.user.id}_{int(time.time())}_{import_file.name}"
            
            try:
                t_save_start = time.time()
                print(f"[DEBUG] Guardando archivo en storage: {filename}...")
                sys.stdout.flush()
                path = default_storage.save(filename, import_file)
                print(f"[DEBUG] Archivo guardado en {time.time() - t_save_start:.2f}s")
                sys.stdout.flush()
            except Exception as e:
                print(f"[DEBUG] Error al guardar archivo: {str(e)}")
                sys.stdout.flush()
                return JsonResponse({'status': 'error', 'message': f'Error al guardar archivo: {str(e)}'}, status=500)
            
            file_format = os.path.splitext(import_file.name)[1][1:].lower()
            
            # Set explicit initial state
            cache_key = f"import_ordenes_progress_{request.user.id}"
            cache.set(cache_key, {
                'current': 0, 'total': 0, 
                'status': 'Iniciando tarea en segundo plano...', 
                'percent': 1
            }, 3600)

            from .tasks import import_ordenes_task
            try:
                t_task_start = time.time()
                print(f"[DEBUG] Enviando tarea a Celery... (Broker: {os.environ.get('CELERY_BROKER_URL', 'default')})")
                sys.stdout.flush()
                task = import_ordenes_task.delay(path, file_format, request.user.id)
                print(f"[DEBUG] Tarea enviada en {time.time() - t_task_start:.2f}s | Task ID: {task.id}")
                sys.stdout.flush()
            except Exception as e:
                print(f"[DEBUG] Error al enviar tarea a Celery: {str(e)}")
                sys.stdout.flush()
                return JsonResponse({'status': 'error', 'message': f'Error de Celery: {str(e)}'}, status=500)
            
            print(f"[DEBUG] import_process_view finalizado en {time.time() - start_time:.2f}s")
            sys.stdout.flush()
            return JsonResponse({'status': 'started', 'task_id': task.id})
        
        return JsonResponse({'status': 'error', 'message': 'No se recibió ningún archivo'}, status=400)

    def import_progress_api(self, request):
        """Endpoint para consultar el progreso en Redis/Caché"""
        from django.core.cache import cache
        cache_key = f"import_ordenes_progress_{request.user.id}"
        data = cache.get(cache_key)
        if not data:
            return JsonResponse({'status': 'waiting', 'message': 'Esperando inicio de tarea...'})
        return JsonResponse(data)

    def test_connectivity(self, request):
        """Vista de diagnostico AVANZADA con DNS check"""
        import socket
        import redis
        from django.conf import settings
        
        results = {}
        target_url = getattr(settings, 'CELERY_BROKER_URL', '')
        results['testing_url'] = target_url
        
        # 1. Analizar URL
        try:
            if '://' in target_url:
                # redis://user:pass@host:port/db
                parts = target_url.split('@')[-1].split('/')[0] # host:port
                if ':' in parts:
                    host = parts.split(':')[0]
                    port = int(parts.split(':')[1])
                else:
                    host = parts
                    port = 6379
            else:
                host = 'localhost'
                port = 6379
                
            results['parsed_host'] = host
            results['parsed_port'] = port
            
            # 2. Test DNS
            try:
                ip = socket.gethostbyname(host)
                results['dns_resolution'] = f"OK -> {ip}"
            except Exception as e:
                results['dns_resolution'] = f"FAIL: {str(e)}"
                
            # 3. Test Ping (Strict Timeout)
            try:
                r = redis.Redis(
                    host=host, 
                    port=port, 
                    password=target_url.split(':')[2].split('@')[0] if '@' in target_url else None,
                    socket_connect_timeout=2, 
                    socket_timeout=2
                )
                if r.ping():
                    results['redis_ping'] = "PONG (Success)"
            except Exception as e:
                results['redis_ping'] = f"FAIL: {str(e)}"

            # 4. Test redis.from_url (What Django uses)
            try:
                r_from_url = redis.from_url(
                    target_url, 
                    socket_connect_timeout=2, 
                    socket_timeout=2
                )
                if r_from_url.ping():
                    results['redis_from_url'] = "PONG (Success)"
            except Exception as e:
                results['redis_from_url'] = f"FAIL: {str(e)}"

        except Exception as e:
            results['parsing_error'] = str(e)

        return JsonResponse(results)

    def pure_ping(self, request):
        """Vista que no toca nada, solo para confirmar que Django vive"""
        return HttpResponse("PONG - Server is alive and responding!")
