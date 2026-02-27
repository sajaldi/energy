from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Servicio, KPI
from .resources import ServicioResource, KPIResource

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
    list_display = ('nombre', 'servicio', 'descripcion', 'forma_de_cumplimiento', 'estado')
    list_filter = ('servicio', 'categoria', 'estado', 'fecha_medicion')
    search_fields = ('nombre', 'descripcion', 'servicio__nombre', 'forma_de_cumplimiento', 'metodo_de_supervision')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
    ordering = ('nombre', 'servicio')

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
