from django.contrib import admin
from .models import Material, StockRecord, CompatibilidadMaterial, MovimientoInventario

class StockRecordInline(admin.TabularInline):
    model = StockRecord
    extra = 0
    readonly_fields = ['cantidad', 'actualizado_en']

class CompatibilidadMaterialInline(admin.TabularInline):
    model = CompatibilidadMaterial
    extra = 1

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ['sku', 'nombre', 'unidad_medida', 'precio_estimado', 'get_stock_total']
    search_fields = ['nombre', 'sku', 'descripcion']
    list_filter = ['unidad_medida']
    inlines = [StockRecordInline, CompatibilidadMaterialInline]
    
    def get_stock_total(self, obj):
        return sum(s.cantidad for s in obj.existencias.all())
    get_stock_total.short_description = "Stock Total"

@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ['fecha_movimiento', 'material', 'tipo', 'cantidad', 'get_ubicacion', 'usuario']
    list_filter = ['tipo', 'fecha_movimiento']
    search_fields = ['material__nombre', 'orden_trabajo__id']
    autocomplete_fields = ['material', 'orden_trabajo']
    
    def get_ubicacion(self, obj):
        if obj.tipo == 'ENTRADA':
            return f"-> {obj.ubicacion_destino}"
        elif obj.tipo == 'SALIDA':
            return f"<- {obj.ubicacion_origen}"
        elif obj.tipo == 'TRASLADO':
            return f"{obj.ubicacion_origen} -> {obj.ubicacion_destino}"
        return f"Ajuste en {obj.ubicacion_destino}"
    get_ubicacion.short_description = "Origen/Destino"

@admin.register(StockRecord)
class StockRecordAdmin(admin.ModelAdmin):
    list_display = ['material', 'ubicacion', 'cantidad', 'actualizado_en']
    list_filter = ['ubicacion']
    search_fields = ['material__nombre']
    readonly_fields = ['actualizado_en']
