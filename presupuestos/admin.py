from django.contrib import admin
from django.utils.html import format_html
from .models import PresupuestoAnual, PartidaPresupuestaria, GastoEjecutado, ItemPresupuesto

class GastoEjecutadoInline(admin.TabularInline):
    model = GastoEjecutado
    extra = 1
    fields = ('fecha', 'descripcion', 'monto', 'referencia')

class ItemPresupuestoInline(admin.TabularInline):
    model = ItemPresupuesto
    extra = 1
    fields = ('concepto', 'ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')

@admin.register(PartidaPresupuestaria)
class PartidaPresupuestariaAdmin(admin.ModelAdmin):
    list_display = ('disciplina', 'presupuesto_anual', 'get_proyectado', 'get_ejecutado', 'get_progreso', 'get_saldo')
    list_filter = ('presupuesto_anual', 'disciplina')
    search_fields = ('disciplina__nombre', 'descripcion')
    inlines = [ItemPresupuestoInline, GastoEjecutadoInline]
    autocomplete_fields = ('disciplina', 'presupuesto_anual')

    def get_proyectado(self, obj):
        return format_html("<b>{}</b>", f"{obj.monto_proyectado:,.2f}")
    get_proyectado.short_description = "Proyectado"

    def get_ejecutado(self, obj):
        return f"{obj.total_ejecutado:,.2f}"
    get_ejecutado.short_description = "Ejecutado"

    def get_saldo(self, obj):
        saldo = obj.saldo_disponible
        color = "#10B981" if saldo >= 0 else "#EF4444"
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, f"{saldo:,.2f}")
    get_saldo.short_description = "Saldo"

    def get_progreso(self, obj):
        percent = 0
        if obj.monto_proyectado > 0:
            percent = int((obj.total_ejecutado / obj.monto_proyectado) * 100)
        
        color = "#3B82F6"
        if percent > 90: color = "#F59E0B"
        if percent > 100: color = "#EF4444"
        
        return format_html(
            '<div style="width: 100px; background: #e2e8f0; border-radius: 4px; height: 12px; position: relative;">'
            '<div style="width: {}px; background: {}; border-radius: 4px; height: 100%;"></div>'
            '<span style="position: absolute; right: -35px; top: -3px; font-size: 10px;">{}%</span>'
            '</div>',
            min(percent, 100), color, percent
        )
    get_progreso.short_description = "% Ejercicio"

class PartidaInline(admin.TabularInline):
    model = PartidaPresupuestaria
    extra = 1
    fields = ('disciplina', 'monto_proyectado', 'descripcion')
    autocomplete_fields = ('disciplina',)

@admin.register(PresupuestoAnual)
class PresupuestoAnualAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'anio', 'moneda', 'get_total_proyectado', 'get_total_ejecutado', 'get_progreso', 'ver_matriz', 'estado')
    list_filter = ('anio', 'estado', 'moneda')
    search_fields = ('nombre',)
    inlines = [PartidaInline]
    
    def get_total_proyectado(self, obj):
        return format_html("<b>{} {}</b>", obj.moneda, f"{obj.total_proyectado:,.2f}")
    get_total_proyectado.short_description = "Total Proyectado"

    def get_total_ejecutado(self, obj):
        return f"{obj.total_ejecutado:,.2f}"
    get_total_ejecutado.short_description = "Total Ejecutado"

    def get_progreso(self, obj):
        percent = obj.porcentaje_ejecucion
        color = "#10B981"
        if percent > 80: color = "#F59E0B"
        if percent > 100: color = "#EF4444"
        
        return format_html(
            '<div style="width: 120px; background: #f1f5f9; border-radius: 10px; height: 18px; border: 1px solid #cbd5e1; overflow: hidden;">'
            '<div style="width: {}%; background: {}; height: 100%; transition: width 0.5s;"></div>'
            '<span style="position: absolute; width: 100%; text-align: center; left: 0; top: 0; font-size: 11px; font-weight: bold; color: #1e293b; line-height: 18px;">{}%</span>'
            '</div>',
            min(percent, 100), color, percent
        )
    def ver_matriz(self, obj):
        from django.urls import reverse
        url = reverse('presupuestos:matriz_detalle', args=[obj.pk])
        return format_html('<a class="button" href="{}" target="_blank" style="background: #6366f1; color: white;">📊 Ver Matriz</a>', url)
    ver_matriz.short_description = "Matriz"

    class Media:
        css = {
            'all': ('core/css/admin_custom.css',)
        }
