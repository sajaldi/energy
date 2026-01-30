from django.contrib import admin
from .models import Servicio, KPI

@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'activo', 'fecha_creacion')
    list_filter = ('activo', 'fecha_creacion')
    search_fields = ('nombre', 'codigo', 'descripcion')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
    ordering = ('nombre',)

@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'servicio', 'tipo', 'meta', 'valor_actual', 'fecha_medicion', 'get_cumplimiento')
    list_filter = ('servicio', 'tipo', 'fecha_medicion')
    search_fields = ('nombre', 'descripcion', 'servicio__nombre')
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')
    ordering = ('-fecha_medicion', 'servicio')
    
    def get_cumplimiento(self, obj):
        percent = obj.porcentaje_cumplimiento
        color = 'green' if percent >= 100 else 'orange' if percent >= 80 else 'red'
        from django.utils.html import format_html
        return format_html('<b style="color: {};">{:.2f}%</b>', color, percent)
    
    get_cumplimiento.short_description = '% Cumplimiento'
