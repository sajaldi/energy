from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Servicio, KPI, ChecklistItem, Auditoria, AuditoriaResultado
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

@admin.register(Servicio)
class ServicioAdmin(ImportExportModelAdmin):
    resource_class = ServicioResource
    list_display = ('nombre', 'codigo', 'activo', 'fecha_creacion')
    list_filter = ('activo', 'fecha_creacion')
    search_fields = ('nombre', 'codigo', 'descripcion')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
    ordering = ('nombre',)

@admin.register(KPI)
class KPIAdmin(ImportExportModelAdmin):
    resource_class = KPIResource
    change_list_template = "admin/mantenimiento/procedimiento/change_list.html" 
    list_display = ('nombre', 'servicio', 'descripcion', 'forma_de_cumplimiento', 'estado', 'comentarios', 'editar_fiori')
    list_filter = ('servicio', 'categoria', 'estado', 'fecha_medicion')
    search_fields = ('nombre', 'descripcion', 'servicio__nombre', 'forma_de_cumplimiento', 'metodo_de_supervision')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
    filter_horizontal = ('rutinas',)
    ordering = ('nombre', 'servicio')
    inlines = [ChecklistItemInline, DocumentoRelacionadoInline]

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
