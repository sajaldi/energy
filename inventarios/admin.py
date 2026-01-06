from django.contrib import admin
from django.contrib import messages
from .models import Material, StockRecord, MovimientoInventario

class StockRecordInline(admin.TabularInline):
    model = StockRecord
    extra = 0
    readonly_fields = ('actualizado_en',)

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('sku', 'nombre', 'unidad_medida', 'get_stock_total', 'precio_estimado')
    search_fields = ('nombre', 'sku', 'descripcion')
    list_filter = ('unidad_medida',)
    inlines = [StockRecordInline]

    def get_queryset(self, request):
        from django.db.models import Sum
        qs = super().get_queryset(request)
        return qs.annotate(db_stock_total=Sum('existencias__cantidad'))

    def get_stock_total(self, obj):
        return obj.db_stock_total if obj.db_stock_total is not None else 0
    get_stock_total.short_description = 'Stock Total'
    get_stock_total.admin_order_field = 'db_stock_total'

@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('fecha_movimiento', 'material', 'tipo', 'cantidad', 'ubicacion_origen', 'ubicacion_destino', 'estado', 'usuario')
    list_filter = ('estado', 'tipo', 'fecha_movimiento')
    search_fields = ('material__nombre', 'material__sku', 'usuario__username', 'orden_trabajo__id')
    readonly_fields = ('fecha_movimiento', 'fecha_aprobacion', 'aprobado_por')
    
    actions = ['liquidar_movimientos']

    def liquidar_movimientos(self, request, queryset):
        # Verificar permiso
        if not request.user.has_perm('inventarios.can_liquidar_movimiento') and not request.user.is_superuser:
            self.message_user(request, "No tienes permiso para liquidar movimientos.", level=messages.ERROR)
            return

        procesados = 0
        errores = 0
        
        for mov in queryset:
            if mov.estado != 'PENDIENTE':
                continue
                
            try:
                mov.liquidar(request.user)
                procesados += 1
            except ValueError as e:
                errores += 1
                self.message_user(request, f"Error en ID {mov.id}: {str(e)}", level=messages.ERROR)
        
        if procesados > 0:
            self.message_user(request, f"{procesados} movimientos liquidados exitosamente.", level=messages.SUCCESS)
        if errores > 0:
            self.message_user(request, f"{errores} movimientos no pudieron ser liquidados por falta de stock.", level=messages.WARNING)

    liquidar_movimientos.short_description = "Liquidar / Aprobar Movimientos Seleccionados"
