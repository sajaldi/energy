from django.contrib import admin
from django.utils.html import format_html
from .models import AnalisisCostoUnitario, DetalleCostoUnitario, FactorCosto


class DetalleInline(admin.TabularInline):
    model = DetalleCostoUnitario
    extra = 1
    autocomplete_fields = ['material']
    fields = ['tipo_recurso', 'material', 'descripcion', 'unidad', 'cantidad', 'precio_unitario', 'factor_rendimiento', 'orden']
    ordering = ['orden', 'id']


class FactorInline(admin.TabularInline):
    model = FactorCosto
    extra = 1
    ordering = ['orden', 'id']


@admin.register(AnalisisCostoUnitario)
class AnalisisCostoUnitarioAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'unidad', 'version', 'estado', 'proyecto', 'costo_directo_resumen', 'costo_total_resumen']
    list_filter = ['estado', 'creado_en']
    search_fields = ['codigo', 'nombre', 'descripcion']
    autocomplete_fields = ['unidad', 'proyecto', 'creado_por', 'aprobado_por']
    readonly_fields = ['codigo', 'version', 'creado_en', 'actualizado_en', 'costo_directo_resumen', 'costo_total_resumen']
    fieldsets = [
        (None, {
            'fields': ['codigo', 'nombre', 'descripcion', 'unidad', 'estado']
        }),
        ('Vinculación', {
            'fields': ['proyecto'],
            'classes': ['collapse']
        }),
        ('Costos', {
            'fields': ['costo_directo_resumen', 'costo_total_resumen'],
            'classes': ['collapse']
        }),
        ('Auditoría', {
            'fields': ['version', 'creado_por', 'aprobado_por', 'fecha_aprobacion', 'creado_en', 'actualizado_en'],
            'classes': ['collapse']
        }),
    ]
    inlines = [DetalleInline, FactorInline]

    def costo_directo_resumen(self, obj):
        if obj.pk:
            return f"{obj.costo_directo_total:,.2f}"
        return "—"
    costo_directo_resumen.short_description = "Costo Directo"

    def costo_total_resumen(self, obj):
        if obj.pk:
            return format_html(
                '<strong>{:,.2f}</strong>',
                obj.costo_total
            )
        return "—"
    costo_total_resumen.short_description = "Costo Total"


@admin.register(DetalleCostoUnitario)
class DetalleCostoUnitarioAdmin(admin.ModelAdmin):
    list_display = ['analisis', 'display_nombre', 'tipo_recurso', 'unidad', 'cantidad', 'precio_unitario', 'total_parcial']
    list_filter = ['tipo_recurso', 'analisis']
    search_fields = ['descripcion', 'material__nombre']
    autocomplete_fields = ['material', 'analisis', 'unidad']


@admin.register(FactorCosto)
class FactorCostoAdmin(admin.ModelAdmin):
    list_display = ['analisis', 'nombre', 'tipo', 'valor']
    list_filter = ['tipo']
    search_fields = ['nombre', 'analisis__nombre']
