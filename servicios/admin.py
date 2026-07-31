from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Servicio, KPI, ChecklistItem, Auditoria, AuditoriaResultado, KPIArchivo
from .models_riesgos import Riesgo
from .resources import ServicioResource, KPIResource
from django.contrib.contenttypes.admin import GenericTabularInline
from documentos.models import MetadatoValor
from django.utils.html import format_html
from django.urls import reverse

class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 0
    fields = ('descripcion', 'completado', 'orden')
    ordering = ('orden',)

class DocumentoRelacionadoInline(GenericTabularInline):
    model = MetadatoValor
    extra = 0
    verbose_name = "Documento Relacionado"
    verbose_name_plural = "Documentos Relacionados"
    fields = ('get_documento_link', 'get_tipo_documento', 'config')
    readonly_fields = ('get_documento_link', 'get_tipo_documento', 'config')
    can_delete = False
    
    def get_documento_link(self, obj):
        if obj.documento:
            url = reverse('admin:documentos_documento_change', args=[obj.documento.id])
            return format_html('<a href="{}" style="font-weight: bold; color: #2563eb;">{}</a>', url, obj.documento.titulo)
        return "-"
    get_documento_link.short_description = "Documento"

    def get_tipo_documento(self, obj):
        return obj.documento.tipo_documento if obj.documento else "-"
    get_tipo_documento.short_description = "Tipo"

    def has_add_permission(self, request, obj=None):
        return False

class RiesgoResumenInline(admin.TabularInline):
    """
    Inline de solo lectura en ServicioAdmin que muestra un resumen de riesgos
    por Zona_Riesgo con enlace a la Matriz de Riesgos del Servicio.
    Requirement 11.3.
    """
    model = Riesgo
    verbose_name = "Resumen de Riesgos"
    verbose_name_plural = "Resumen de Riesgos"
    fields = ('codigo', 'titulo', 'categoria', 'estado_apetito', 'estado_revision')
    readonly_fields = ('codigo', 'titulo', 'categoria', 'estado_apetito', 'estado_revision')
    extra = 0
    can_delete = False
    show_change_link = True
    max_num = 10

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Servicio)
class ServicioAdmin(ImportExportModelAdmin):
    resource_class = ServicioResource
    list_display = ('nombre', 'codigo', 'activo', 'fecha_creacion')
    list_filter = ('activo', 'fecha_creacion')
    search_fields = ('nombre', 'codigo', 'descripcion')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion', 'resumen_riesgos_link')
    ordering = ('nombre',)
    inlines = [RiesgoResumenInline]

    def resumen_riesgos_link(self, obj):
        """
        Muestra un resumen de conteo de riesgos por Zona_Riesgo y un enlace
        a la Matriz de Riesgos del Servicio.
        """
        if not obj.pk:
            return "-"
        riesgos = obj.riesgos.filter(estado='ACTIVO')
        total = riesgos.count()
        if total == 0:
            return format_html('<span style="color:#888;">Sin riesgos activos registrados</span>')

        # Conteo por zona usando la última evaluación residual de cada riesgo
        from django.db.models import Count, Q
        from .models_riesgos import EvaluacionRiesgo

        # Contar por zona basándose en el campo de la última evaluación
        # Usamos las evaluaciones residuales para obtener zona real
        conteo = {
            'BAJO': 0,
            'MEDIO': 0,
            'ALTO': 0,
            'CRITICO': 0,
        }
        for riesgo in riesgos:
            ultima_eval = riesgo.evaluaciones.filter(tipo='RESIDUAL').order_by('-fecha_evaluacion').first()
            if ultima_eval:
                zona = ultima_eval.zona_riesgo
            else:
                ultima_eval_inh = riesgo.evaluaciones.filter(tipo='INHERENTE').order_by('-fecha_evaluacion').first()
                zona = ultima_eval_inh.zona_riesgo if ultima_eval_inh else 'BAJO'
            conteo[zona] = conteo.get(zona, 0) + 1

        colores = {
            'BAJO': '#28a745',
            'MEDIO': '#ffc107',
            'ALTO': '#fd7e14',
            'CRITICO': '#dc3545',
        }
        etiquetas = {
            'BAJO': 'Bajo',
            'MEDIO': 'Medio',
            'ALTO': 'Alto',
            'CRITICO': 'Crítico',
        }

        badges = []
        for zona in ('BAJO', 'MEDIO', 'ALTO', 'CRITICO'):
            cantidad = conteo[zona]
            if cantidad > 0:
                badges.append(
                    f'<span style="background:{colores[zona]};color:#fff;padding:2px 8px;'
                    f'border-radius:4px;font-size:11px;font-weight:600;margin-right:4px;">'
                    f'{etiquetas[zona]}: {cantidad}</span>'
                )

        resumen = ''.join(badges)
        resumen += f'<br><small style="color:#555;">Total activos: {total}</small>'

        # Enlace a la Matriz de Riesgos (URL futura, usa admin changelist filtrado por ahora)
        try:
            url_matriz = reverse('admin:servicios_riesgo_changelist') + f'?servicio__id__exact={obj.pk}'
            resumen += (
                f'<br><a href="{url_matriz}" style="color:#0a6ed1;font-weight:600;'
                f'font-size:12px;text-decoration:none;">'
                f'📊 Ver Matriz de Riesgos</a>'
            )
        except Exception:
            pass

        return format_html(resumen)

    resumen_riesgos_link.short_description = "Resumen de Riesgos"

class KPIArchivoInline(admin.TabularInline):
    model = KPIArchivo
    extra = 0
    fields = ('nombre', 'archivo', 'subido_por', 'creado_en')
    readonly_fields = ('subido_por', 'creado_en')

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(KPI)
class KPIAdmin(ImportExportModelAdmin):
    resource_class = KPIResource
    change_list_template = "admin/mantenimiento/procedimiento/change_list.html" 
    list_display = ('nombre', 'servicio', 'descripcion', 'forma_de_cumplimiento', 'estado', 'comentarios', 'editar_fiori')
    list_filter = ('servicio', 'categoria', 'estado', 'fecha_medicion')
    search_fields = ('nombre', 'descripcion', 'servicio__nombre', 'forma_de_cumplimiento', 'metodo_de_supervision')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion', 'riesgos_vinculados_display')
    filter_horizontal = ('rutinas',)
    ordering = ('nombre', 'servicio')
    inlines = [ChecklistItemInline, DocumentoRelacionadoInline, KPIArchivoInline]

    def changelist_view(self, request, extra_context=None):
        from .views import kpi_dashboard_view
        return kpi_dashboard_view(request)

    def editar_fiori(self, obj):
        url = reverse('servicios:kpi_form_edit', args=[obj.pk])
        return format_html(
            '<a href="{}" style="background:#0a6ed1;color:#fff;padding:5px 12px;border-radius:6px;'
            'font-size:12px;font-weight:600;text-decoration:none;display:inline-flex;align-items:center;gap:4px;">'
            '<i class="fas fa-pen" style="font-size:10px;"></i> Editar</a>', url
        )
    editar_fiori.short_description = "Acciones"

    def riesgos_vinculados_display(self, obj):
        """
        Muestra los Riesgos vinculados al KPI con badge de Zona_Riesgo,
        ordenados por nivel_riesgo descendente (última evaluación residual).
        Requirement 7.5.
        """
        if not obj.pk:
            return "-"

        from .models_riesgos import EvaluacionRiesgo
        from django.db.models import Subquery, OuterRef

        # Subquery to get the latest residual evaluation's nivel_riesgo for each riesgo
        ultima_eval = (
            EvaluacionRiesgo.objects
            .filter(riesgo=OuterRef('pk'), tipo='RESIDUAL')
            .order_by('-fecha_evaluacion')
            .values('nivel_riesgo')[:1]
        )

        riesgos = (
            obj.riesgos_asociados
            .filter(estado='ACTIVO')
            .annotate(nivel_residual=Subquery(ultima_eval))
            .order_by('-nivel_residual')
        )

        if not riesgos.exists():
            return format_html('<span style="color:#888;">Sin riesgos vinculados</span>')

        colores_zona = {
            'BAJO': '#28a745',
            'MEDIO': '#ffc107',
            'ALTO': '#fd7e14',
            'CRITICO': '#dc3545',
        }
        etiquetas_zona = {
            'BAJO': 'Bajo',
            'MEDIO': 'Medio',
            'ALTO': 'Alto',
            'CRITICO': 'Crítico',
        }

        items = []
        for riesgo in riesgos:
            # Get zona from latest residual evaluation
            ultima = riesgo.evaluaciones.filter(tipo='RESIDUAL').order_by('-fecha_evaluacion').first()
            if ultima:
                zona = ultima.zona_riesgo
            else:
                ultima_inh = riesgo.evaluaciones.filter(tipo='INHERENTE').order_by('-fecha_evaluacion').first()
                zona = ultima_inh.zona_riesgo if ultima_inh else 'BAJO'

            color = colores_zona.get(zona, '#6c757d')
            etiqueta = etiquetas_zona.get(zona, zona)
            text_color = '#000' if zona == 'MEDIO' else '#fff'
            badge = (
                f'<span style="background:{color};color:{text_color};padding:2px 6px;'
                f'border-radius:3px;font-size:10px;font-weight:600;">'
                f'{etiqueta}</span>'
            )
            items.append(
                f'<li style="margin-bottom:4px;">'
                f'{badge} '
                f'<span style="font-size:12px;">{riesgo.codigo} - {riesgo.titulo}</span>'
                f'</li>'
            )

        html = (
            f'<ul style="list-style:none;padding:0;margin:0;">'
            f'{"".join(items)}'
            f'</ul>'
        )
        return format_html(html)

    riesgos_vinculados_display.short_description = "Riesgos Vinculados"


    def get_urls(self):
        urls = super().get_urls()
        from django.urls import path
        from django.views.decorators.csrf import csrf_exempt
        from .views import import_kpis_background, import_kpis_process, import_kpis_progress

        custom_urls = [
            path('import-background/', self.admin_site.admin_view(import_kpis_background), name='servicios_kpi_import_background'),
            path('import-background/process/', csrf_exempt(self.admin_site.admin_view(import_kpis_process)), name='servicios_kpi_import_process'),
            path('import-background/progress/', self.admin_site.admin_view(import_kpis_progress), name='servicios_kpi_import_progress'),
            path('import-background/template/', self.admin_site.admin_view(self.download_template_view), name='servicios_kpi_import_template'),
        ]
        return custom_urls + urls

    def download_template_view(self, request):
        from django.http import HttpResponse
        from .models import KPI
        dataset = KPIResource().export(queryset=KPI.objects.none())
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="plantilla_importacion_kpis.xlsx"'
        return response


class AuditoriaResultadoInline(admin.TabularInline):
    model = AuditoriaResultado
    extra = 0
    autocomplete_fields = ['kpi']

@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'fecha', 'fecha_creacion')
    list_filter = ('fecha',)
    search_fields = ('nombre', 'descripcion')
    inlines = [AuditoriaResultadoInline]


from .admin_riesgos import *  # noqa
