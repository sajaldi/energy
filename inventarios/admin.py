from django.contrib import admin
from django.contrib import messages
from django.urls import path
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin
from .models import Material, StockRecord, MovimientoInventario, CategoriaMaterial, SolicitudMaterial
from activos.models import Marca

class StockRecordInline(admin.TabularInline):
    model = StockRecord
    extra = 0
    readonly_fields = ('actualizado_en',)

@admin.register(CategoriaMaterial)
class CategoriaMaterialAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'padre')
    search_fields = ('nombre',)
    list_filter = ('padre',)

class MovimientoInventarioInline(admin.TabularInline):
    model = MovimientoInventario
    extra = 0
    raw_id_fields = ('material', 'ubicacion_origen', 'ubicacion_destino')

@admin.register(SolicitudMaterial)
class SolicitudMaterialAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'fecha_solicitud', 'estado', 'ubicacion_origen')
    list_filter = ('estado', 'fecha_solicitud')
    search_fields = ('usuario__username', 'items__material__nombre')
    inlines = [MovimientoInventarioInline]

class MaterialResource(resources.ModelResource):
    categoria = fields.Field(
        column_name='categoria',
        attribute='categoria',
        widget=ForeignKeyWidget(CategoriaMaterial, 'nombre')
    )
    marca = fields.Field(
        column_name='marca',
        attribute='marca',
        widget=ForeignKeyWidget(Marca, 'nombre')
    )

    class Meta:
        model = Material
        import_id_fields = ('sku',)
        fields = ('sku', 'nombre', 'marca', 'descripcion', 'categoria', 'unidad_medida', 'precio_estimado', 'stock_minimo')
        export_order = fields

    def before_import_row(self, row, **kwargs):
        """Limpia datos y auto-crea categorías/marcas para facilitar la importación."""
        for key in list(row.keys()):
            val = row.get(key)
            if val is None:
                continue
            
            val_str = str(val).strip()
            if val_str.lower() in ['none', 'nan', 'null', '']:
                row[key] = None
            else:
                if isinstance(val, str):
                    row[key] = val.strip()
                else:
                    row[key] = val_str
        
        # Auto-crear Categoría
        cat_nombre = row.get('categoria')
        if cat_nombre:
            CategoriaMaterial.objects.get_or_create(nombre=cat_nombre.strip())
            
        # Auto-crear Marca
        marca_nombre = row.get('marca')
        if marca_nombre:
            Marca.objects.get_or_create(nombre=marca_nombre.strip())

    def after_import_row(self, row, instance, **kwargs):
        """
        Procesa stock inicial y compatibilidades de repuestos.
        """
        # 1. Procesar Stock Inicial si viene en el archivo
        stock_inicial = row.get('stock_inicial') or row.get('cantidad_inicial') or row.get('existencias')
        ubicacion_nombre = row.get('ubicacion') or row.get('bodega') or row.get('almacen')
        
        if stock_inicial and ubicacion_nombre:
            from activos.models import Ubicacion
            from decimal import Decimal
            
            try:
                # Buscar ubicación por nombre
                ubicacion = Ubicacion.objects.filter(nombre__iexact=str(ubicacion_nombre).strip()).first()
                if ubicacion:
                    cantidad = Decimal(str(stock_inicial))
                    if cantidad > 0:
                        # Crear o actualizar registro de stock
                        stock, created = StockRecord.objects.get_or_create(
                            material=instance,
                            ubicacion=ubicacion
                        )
                        if created:
                            stock.cantidad = cantidad
                        else:
                            # Si ya existía, sumamos la carga inicial (o podrías decidir sobrescribir)
                            stock.cantidad += cantidad
                        stock.save()
                        
                        # Registrar movimiento de entrada si estamos en importación real (no dry run)
                        if not kwargs.get('dry_run'):
                            MovimientoInventario.objects.create(
                                material=instance,
                                tipo='ENTRADA',
                                cantidad=cantidad,
                                ubicacion_destino=ubicacion,
                                estado='APROBADO',
                                comentarios='Carga inicial desde importación masiva'
                            )
            except Exception as e:
                pass # Errores silenciosos en stock para no romper la importación principal

        # 2. Procesar Compatibilidad (Repuestos para modelos específicos)
        modelos_compatibles = row.get('modelos_compatibles') or row.get('repuesto_para') or row.get('equipos')
        if modelos_compatibles:
            from activos.models import Modelo
            from .models import CompatibilidadMaterial
            
            # Formatos soportados: "Modelo A, Modelo B" o "Modelo A; Modelo B"
            delimitador = ';' if ';' in str(modelos_compatibles) else ','
            nombres = [n.strip() for n in str(modelos_compatibles).split(delimitador) if n.strip()]
            
            for nombre in nombres:
                modelo = Modelo.objects.filter(nombre__iexact=nombre).first()
                if not modelo:
                    # Intentar por código si no por nombre
                    modelo = Modelo.objects.filter(codigo__iexact=nombre).first()
                
                if modelo:
                    CompatibilidadMaterial.objects.get_or_create(
                        material=instance,
                        modelo=modelo
                    )

@admin.register(Material)
class MaterialAdmin(ImportExportModelAdmin):
    change_list_template = 'admin/inventarios/material/change_list.html'
    resource_class = MaterialResource
    list_display = ('sku', 'nombre', 'categoria', 'unidad_medida', 'get_stock_total')
    search_fields = ('nombre', 'sku', 'descripcion')
    list_filter = ('categoria', 'unidad_medida')
    inlines = [StockRecordInline]

    def get_queryset(self, request):
        from django.db.models import Sum
        qs = super().get_queryset(request)
        return qs.annotate(db_stock_total=Sum('existencias__cantidad'))

    def get_stock_total(self, obj):
        return obj.db_stock_total if obj.db_stock_total is not None else 0
    get_stock_total.short_description = 'Stock Total'
    get_stock_total.admin_order_field = 'db_stock_total'

    def get_urls(self):
        urls = super().get_urls()
        from . import views
        custom_urls = [
            path('import-background/', self.admin_site.admin_view(views.import_materiales_background), name='inventarios_material_import_background'),
            path('import-background/process/', csrf_exempt(self.admin_site.admin_view(views.import_materiales_process)), name='inventarios_material_import_process'),
            path('import-background/progress/', self.admin_site.admin_view(views.import_materiales_progress), name='inventarios_material_import_progress'),
            path('import-background/template/', self.admin_site.admin_view(self.download_template_view), name='inventarios_material_import_template'),
        ]
        return custom_urls + urls

    def download_template_view(self, request):
        """Genera un archivo Excel vacío con las cabeceras del recurso de Materiales"""
        dataset = MaterialResource().export(queryset=Material.objects.none())
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="formato_importacion_materiales.xlsx"'
        return response

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
