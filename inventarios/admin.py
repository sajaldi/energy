from django.contrib import admin
from django.contrib import messages
from django.urls import path
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.html import mark_safe
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin
from .models import Material, StockRecord, MovimientoInventario, CategoriaMaterial, SolicitudMaterial, Lote, UnidadMedida, IngresoInventario
from activos.models import Marca

class StockRecordInline(admin.TabularInline):
    model = StockRecord
    extra = 0
    max_num = 10
    can_delete = False
    raw_id_fields = ('lote', 'ubicacion')
    readonly_fields = ('material', 'actualizado_en')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('lote', 'ubicacion')

@admin.register(CategoriaMaterial)
class CategoriaMaterialAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'padre')
    search_fields = ('nombre',)
    list_filter = ('padre',)

@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'material', 'fecha_vencimiento', 'fecha_fabricacion')
    search_fields = ('codigo', 'material__nombre', 'material__sku')
    list_filter = ('fecha_vencimiento',)

@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'abreviatura')
    search_fields = ('nombre', 'abreviatura')

class MovimientoInventarioInline(admin.TabularInline):
    model = MovimientoInventario
    extra = 0
    max_num = 15
    show_change_link = True
    raw_id_fields = ('material', 'ubicacion_origen', 'ubicacion_destino')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('usuario', 'lote')

@admin.register(SolicitudMaterial)
class SolicitudMaterialAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'fecha_solicitud', 'estado', 'ubicacion_origen')
    list_filter = ('estado', 'fecha_solicitud')
    search_fields = ('usuario__username', 'items__material__nombre')
    inlines = [MovimientoInventarioInline]

@admin.register(IngresoInventario)
class IngresoInventarioAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_ingreso', 'usuario', 'ubicacion_destino', 'get_requisicion')
    list_filter = ('fecha_ingreso', 'usuario', 'ubicacion_destino')
    search_fields = ('usuario__username', 'requisicion_origen__cr8ca_requisicion', 'comentarios')
    inlines = [MovimientoInventarioInline]

    def get_requisicion(self, obj):
        return obj.requisicion_origen.cr8ca_requisicion if obj.requisicion_origen else "--"
    get_requisicion.short_description = "Requisición"

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
    unidad_medida = fields.Field(
        column_name='unidad_medida',
        attribute='unidad_medida',
        widget=ForeignKeyWidget(UnidadMedida, 'nombre')
    )

    class Meta:
        model = Material
        import_id_fields = ('sku',)
        fields = ('sku', 'nombre', 'marca', 'descripcion', 'categoria', 'tipo_material', 'unidad_medida', 'precio_estimado', 'stock_minimo', 'imagen')
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

        # Auto-crear Unidad de Medida
        unidad_nombre = row.get('unidad_medida')
        if unidad_nombre:
            UnidadMedida.objects.get_or_create(
                nombre=unidad_nombre.strip(),
                defaults={'abreviatura': unidad_nombre.strip()[:10]}
            )

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
                        # Procesar Lote si viene
                        lote_obj = None
                        lote_codigo = row.get('lote_codigo') or row.get('lote')
                        if lote_codigo:
                            vencimiento = row.get('lote_vencimiento') or row.get('fecha_vencimiento') or row.get('vencimiento')
                            lote_obj, _ = Lote.objects.get_or_create(
                                material=instance,
                                codigo=str(lote_codigo).strip(),
                                defaults={'fecha_vencimiento': vencimiento}
                            )

                        # El registro de movimiento ahora se encarga de crear el StockRecord automáticamente
                        # mediante la señal post_save que ejecuta recalcular_stock()

                        
                        # Registrar movimiento de entrada si estamos en importación real (no dry run)
                        if not kwargs.get('dry_run'):
                            MovimientoInventario.objects.create(
                                material=instance,
                                lote=lote_obj,
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

class MaterialMovimientoInline(admin.TabularInline):
    model = MovimientoInventario
    extra = 0
    max_num = 20
    can_delete = False
    show_change_link = True
    readonly_fields = ('fecha_movimiento', 'tipo', 'cantidad', 'ubicacion_origen', 'ubicacion_destino', 'estado', 'usuario')
    verbose_name = "Historial de Movimiento"
    verbose_name_plural = "Historial de Movimientos"
    ordering = ('-fecha_movimiento',)

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'usuario', 'ubicacion_origen', 'ubicacion_destino', 'lote', 'solicitud'
        )

@admin.register(Material)
class MaterialAdmin(ImportExportModelAdmin):
    change_list_template = 'admin/inventarios/material/change_list.html'
    resource_class = MaterialResource
    list_display = ('sku', 'nombre', 'categoria', 'tipo_material', 'unidad_medida', 'get_stock_total', 'imagen_preview')
    search_fields = ('nombre', 'sku', 'descripcion')
    list_filter = ('categoria', 'tipo_material', 'unidad_medida')
    list_select_related = ('categoria', 'marca')
    filter_horizontal = ('departamentos',)
    inlines = [StockRecordInline, MaterialMovimientoInline]
    readonly_fields = ('imagen_preview',)

    def imagen_preview(self, obj):
        if obj.imagen:
            return mark_safe(f'<img src="{obj.imagen.url}" width="50" height="50" style="object-fit:cover; border-radius:4px;" />')
        else:
             fallback_svg = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='50' height='50' viewBox='0 0 24 24' fill='none' stroke='%233b82f6' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z'%3E%3C/path%3E%3Cpolyline points='3.27 6.96 12 12.01 20.73 6.96'%3E%3C/polyline%3E%3Cline x1='12' y1='22.08' x2='12' y2='12'%3E%3C/line%3E%3C/svg%3E"
             return mark_safe(f'<img src="{fallback_svg}" width="50" height="50" style="object-fit:cover; border-radius:4px; opacity:0.6;" />')
        return "-"
    imagen_preview.short_description = 'Imagen'

    def get_queryset(self, request):
        from django.db.models import Sum
        qs = super().get_queryset(request)
        qs = qs.select_related('categoria', 'marca', 'unidad_medida').prefetch_related('departamentos')
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
    list_display = ('fecha_movimiento', 'material', 'lote', 'tipo', 'cantidad', 'ubicacion_origen', 'ubicacion_destino', 'estado', 'usuario', 'es_inconsistente')
    list_filter = ('estado', 'tipo', 'fecha_movimiento', 'es_inconsistente')
    search_fields = ('material__nombre', 'material__sku', 'usuario__username', 'orden_trabajo__id')
    autocomplete_fields = ('material', 'lote', 'ubicacion_origen', 'ubicacion_destino')
    readonly_fields = ('fecha_movimiento', 'fecha_aprobacion', 'aprobado_por')
    raw_id_fields = ('solicitud', 'orden_trabajo')
    
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
