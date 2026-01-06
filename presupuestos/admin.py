from django.contrib import admin
from django.utils.html import format_html
from .models import (
    PresupuestoAnual, PartidaPresupuestaria, GastoEjecutado, 
    ItemPresupuesto, Compromiso, DetalleCompromiso, CambioPresupuesto, DetallePeriodico
)

class GastoEjecutadoInline(admin.TabularInline):
    model = GastoEjecutado
    extra = 1
    fields = ('fecha', 'descripcion', 'monto', 'referencia', 'compromiso')
    autocomplete_fields = ['compromiso']

class CambioPresupuestoInline(admin.TabularInline):
    model = CambioPresupuesto
    extra = 0
    fields = ('tipo', 'monto', 'descripcion', 'estado')
    classes = ['collapse']

class DetallePeriodicoInline(admin.TabularInline):
    model = DetallePeriodico
    extra = 0
    fields = ('mes', 'monto')

@admin.register(ItemPresupuesto)
class ItemPresupuestoAdmin(admin.ModelAdmin):
    list_display = ('concepto', 'partida', 'es_recurrente', 'frecuencia', 'total_anual')
    list_filter = ('partida__disciplina', 'es_recurrente')
    search_fields = ('concepto',)
    inlines = [DetallePeriodicoInline]
    autocomplete_fields = ['partida']
    
    readonly_fields = ('generar_distribucion_btn',)
    fields = (
        'partida', 'concepto', 
        'es_recurrente', 'frecuencia', 'monto_base', 'mes_inicio', 
        'generar_distribucion_btn'
    )
    
    def get_urls(self):
        urls = super().get_urls()
        from django.urls import path
        custom_urls = [
            path(
                '<int:item_id>/generar-distribucion/',
                self.admin_site.admin_view(self.generar_distribucion_view),
                name='presupuestos_itempresupuesto_generar',
            ),
        ]
        return custom_urls + urls

    def generar_distribucion_btn(self, obj):
        if obj.pk:
            from django.urls import reverse
            url = reverse('admin:presupuestos_itempresupuesto_generar', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="background-color: #2563eb; color: white;">⚡ Generar Distribución Mensual</a>', 
                url
            )
        return "Guarde primero para generar."
    generar_distribucion_btn.short_description = "Acciones"
    generar_distribucion_btn.allow_tags = True

    def generar_distribucion_view(self, request, item_id):
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        
        item = get_object_or_404(ItemPresupuesto, pk=item_id)
        
        item._generar_detalles()
        
        self.message_user(request, f"Distribución generada para '{item.concepto}' exitosamente.", messages.SUCCESS)
        return redirect('admin:presupuestos_itempresupuesto_change', item.pk)

class ItemPresupuestoInline(admin.TabularInline):
    model = ItemPresupuesto
    extra = 1
    fields = ('concepto', 'es_recurrente', 'frecuencia', 'monto_base', 'mes_inicio')
    show_change_link = True # Allow editing children via link

@admin.register(PartidaPresupuestaria)
class PartidaPresupuestariaAdmin(admin.ModelAdmin):
    list_display = (
        'disciplina', 
        'presupuesto_anual', 
        'get_original',
        'get_cambios',
        'get_vigente', 
        'get_comprometido',
        'get_gastado', 
        'get_disponible'
    )
    list_filter = ('presupuesto_anual', 'disciplina')
    search_fields = ('disciplina__nombre', 'descripcion')
    inlines = [CambioPresupuestoInline, GastoEjecutadoInline, ItemPresupuestoInline]
    autocomplete_fields = ('disciplina', 'presupuesto_anual')

    def get_original(self, obj):
        return format_html("<b>{}</b>", f"{obj.monto_proyectado:,.2f}")
    get_original.short_description = "Original"

    def get_cambios(self, obj):
        val = obj.total_cambios_aprobados
        color = "black" if val >= 0 else "red"
        return format_html('<span style="color:{}">{}</span>', color, f"{val:,.2f}")
    get_cambios.short_description = "Cambios Ap."

    def get_vigente(self, obj):
        return format_html("<b>{}</b>", f"{obj.presupuesto_vigente:,.2f}")
    get_vigente.short_description = "Vigente"

    def get_comprometido(self, obj):
        return f"{obj.total_comprometido:,.2f}"
    get_comprometido.short_description = "Comprometido"

    def get_gastado(self, obj):
        return f"{obj.total_gastado:,.2f}"
    get_gastado.short_description = "Facturado"

    def get_disponible(self, obj):
        saldo = obj.pendiente_comprometer
        color = "#10B981" if saldo >= 0 else "#EF4444"
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, f"{saldo:,.2f}")
    get_disponible.short_description = "Por Comprometer"


class PartidaInline(admin.TabularInline):
    model = PartidaPresupuestaria
    extra = 1
    fields = ('disciplina', 'monto_proyectado', 'descripcion', 'editar_detalles')
    readonly_fields = ('editar_detalles',)
    autocomplete_fields = ('disciplina',)

    def editar_detalles(self, obj):
        if obj.pk:
            from django.urls import reverse
            url = reverse('admin:presupuestos_partidapresupuestaria_change', args=[obj.pk])
            return format_html('<a href="{}" target="_blank" class="button">📝 Gestionar Items y Recurrencia</a>', url)
        return "-"
    editar_detalles.short_description = "Detalles"

@admin.register(PresupuestoAnual)
class PresupuestoAnualAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'anio', 'moneda', 'get_total_proyectado', 'get_total_ejecutado', 'get_progreso', 'ver_cronograma_btn', 'estado')
    list_filter = ('anio', 'estado', 'moneda')
    search_fields = ('nombre',)
    inlines = [PartidaInline]
    
    def ver_cronograma_btn(self, obj):
        from django.urls import reverse
        url = reverse('presupuestos:cronograma_detalle', args=[obj.pk])
        return format_html('<a class="button" href="{}" target="_blank" style="background: #6366f1; color: white;">📅 Cronograma</a>', url)
    ver_cronograma_btn.short_description = "Vista Visual"
    
    def get_total_proyectado(self, obj):
        return format_html("<b>{} {}</b>", obj.moneda, f"{obj.total_proyectado:,.2f}")
    get_total_proyectado.short_description = "Total Original"

    def get_total_ejecutado(self, obj):
        return f"{obj.total_ejecutado:,.2f}"
    get_total_ejecutado.short_description = "Total Facturado"

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
    class Media:
        css = {
            'all': ('core/css/admin_custom.css',)
        }

class DetalleCompromisoInline(admin.TabularInline):
    model = DetalleCompromiso
    extra = 1
    autocomplete_fields = ['partida']

@admin.register(Compromiso)
class CompromisoAdmin(admin.ModelAdmin):
    list_display = ('referencia', 'proveedor', 'fecha', 'monto_total', 'estado')
    list_filter = ('estado', 'fecha')
    search_fields = ('referencia', 'proveedor', 'descripcion')
    inlines = [DetalleCompromisoInline]

@admin.register(CambioPresupuesto)
class CambioPresupuestoAdmin(admin.ModelAdmin):
    list_display = ('partida', 'tipo', 'monto', 'estado', 'fecha_aprobacion')
    list_filter = ('tipo', 'estado', 'partida__presupuesto_anual')
    search_fields = ('descripcion', 'partida__disciplina__nombre')
    autocomplete_fields = ['partida']

@admin.register(GastoEjecutado)
class GastoEjecutadoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'descripcion', 'monto', 'partida', 'compromiso')
    list_filter = ('partida__presupuesto_anual', 'fecha')
    search_fields = ('descripcion', 'referencia')
    autocomplete_fields = ['partida', 'compromiso']
