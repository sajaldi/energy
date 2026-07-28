from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from import_export.formats.base_formats import XLSX, CSV
from .models import (
    PresupuestoAnual, PartidaPresupuestaria, GastoEjecutado, 
    ItemPresupuesto, Compromiso, DetalleCompromiso, CambioPresupuesto, DetallePeriodico,
    PresupuestoAgrupado, Requisicion, ArticuloRequisicion, DocumentoRequisicion,
    SolicitudPago, ItemSolicitudPago,
    REPEX, REPEXItem, Moneda,
    OrdenCompra, OrdenCompraArticulo, CentroCosto,
    Cotizacion, ItemCotizacion, ItemPredefinido,
    CodigoExoneracion,
)
from .resources import RequisicionResource, CodigoExoneracionResource

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
    filter_horizontal = ('departamentos',)
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

@admin.register(Moneda)
class MonedaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'simbolo')
    search_fields = ('nombre', 'codigo')

@admin.register(PresupuestoAnual)
class PresupuestoAnualAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'anio', 'departamento', 'moneda', 'get_total_proyectado', 'get_total_ejecutado', 'get_progreso', 'ver_cronograma_btn', 'estado', 'elaborado_por')
    list_filter = ('anio', 'estado', 'moneda', 'departamento')
    search_fields = ('nombre', 'departamento__nombre')
    inlines = [PartidaInline]
    autocomplete_fields = ['elaborado_por', 'departamento', 'moneda']
    
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


@admin.register(PresupuestoAgrupado)
class PresupuestoAgrupadoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'anio', 'get_total_proyectado', 'get_total_ejecutado', 'get_progreso', 'ver_cronograma_btn')
    list_filter = ('anio',)
    search_fields = ('nombre',)
    filter_horizontal = ('presupuestos',)

    def ver_cronograma_btn(self, obj):
        from django.urls import reverse
        url = reverse('presupuestos:cronograma_grupal', args=[obj.pk])
        return format_html('<a class="button" href="{}" target="_blank" style="background: #10b981; color: white;">📊 Ver Análisis Grupal</a>', url)
    ver_cronograma_btn.short_description = "Vista Gerencial"

    def get_total_proyectado(self, obj):
        return f"{obj.total_proyectado:,.2f}"
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

class ArticuloRequisicionInline(admin.TabularInline):
    model = ArticuloRequisicion
    extra = 0
    fields = ('material', 'descripcion_material', 'unidad_medida', 'cr8ca_articulo', 'cr8ca_cantidad', 'cr8ca_costoaproximado', 'subtotal')
    readonly_fields = ('unidad_medida', 'descripcion_material', 'subtotal')
    autocomplete_fields = ['material'] # Enables search for Material
    template = 'admin/presupuestos/requisicion/articulo_inline.html'

    def descripcion_material(self, obj):
        if obj.material:
            return obj.material.descripcion
        return "-"
    descripcion_material.short_description = "Detalle Material"

    def unidad_medida(self, obj):
        if obj.material:
            return obj.material.unidad_medida
        return "-"
    unidad_medida.short_description = "Unidad"



class DocumentoRequisicionInline(admin.TabularInline):
    model = DocumentoRequisicion
    extra = 1
    fields = ('archivo', 'nombre', 'vista_previa_thumbnail', 'previsualizar')
    readonly_fields = ('vista_previa_thumbnail', 'previsualizar')
    template = 'admin/presupuestos/requisicion/document_inline.html'

    class Media:
        css = {
            'all': ('core/css/sharepoint_list.css',)
        }

    def vista_previa_thumbnail(self, obj):
        if obj.archivo:
            ext = obj.archivo.name.lower()
            url = obj.archivo.url
            if any(x in ext for x in ['.jpg', '.jpeg', '.png', '.gif']):
                return format_html('<img src="{}" style="height: 100px; width: auto; border-radius: 4px; border: 1px solid #ddd;" />', url)
            elif '.pdf' in ext:
                return format_html('<embed src="{}" type="application/pdf" width="150" height="200" style="border: 1px solid #ddd;" />', url)
            else:
                return format_html('<span style="color: #666;">Sin vista previa</span>')
        return ""
    vista_previa_thumbnail.short_description = "Vista Previa"

    def previsualizar(self, obj):
        if obj.archivo:
            url = obj.archivo.url
            return format_html(
                '<a href="javascript:void(0)" onclick="window.open(\'{}\', \'popup\', \'width=800,height=600,scrollbars=yes\'); return false;" '
                'class="button" style="background-color: #6366f1; color: white; padding: 5px 10px; border-radius: 4px; font-size: 12px;">'
                '👁️ Ver Documento</a>',
                url
            )
        return "Guarde para previsualizar"
    previsualizar.short_description = "Vista Previa"

@admin.register(Requisicion)
class RequisicionAdmin(ImportExportModelAdmin):
    change_list_template = 'admin/presupuestos/requisicion/change_list.html'
    list_display = ('cr8ca_requisicion', 'fecha', 'partida', 'item_presupuesto', 'tipo_rutina', 'proveedor', 'cr8ca_asunto', 'cr8ca_prioridad', 'cr8ca_totalenarticulos', 'usuario_solicitante', 'createdon')
    list_filter = ('fecha', 'cr8ca_prioridad', 'estado_requisicion')
    search_fields = ('cr8ca_requisicion', 'cr8ca_asunto', 'cr8ca_motivo')
    autocomplete_fields = ['partida', 'item_presupuesto', 'tipo_rutina', 'proveedor', 'usuario_solicitante', 'usuario_en_nombre_de', 'aprobador']
    ordering = ('-fecha',)
    inlines = [ArticuloRequisicionInline, DocumentoRequisicionInline]
    readonly_fields = ('cr8ca_requisicionid', 'cr8ca_requisicion', 'createdon', 'modifiedon', 'total_estimado', 'monto_pagado', 'import_background_btn')
    resource_classes = [RequisicionResource]
    export_formats = [XLSX, CSV]
    list_per_page = 50
    
    def get_urls(self):
        urls = super().get_urls()
        from django.urls import path
        custom_urls = [
            path('import-background/', self.admin_site.admin_view(self.import_background_view), name='presupuestos_requisicion_import_background'),
            path('import-background/template/', self.admin_site.admin_view(self.download_template_view), name='presupuestos_requisicion_import_template'),
            path('import-json/', self.admin_site.admin_view(self.import_json_view), name='presupuestos_requisicion_import_json'),
        ]
        return custom_urls + urls

    def import_background_btn(self, obj=None):
        from django.urls import reverse
        url_bg = reverse('admin:presupuestos_requisicion_import_background')
        url_json = reverse('admin:presupuestos_requisicion_import_json')
        return format_html(
            '<div style="display: flex; gap: 10px;">'
            '<a class="button" href="{}" style="background-color: #10b981; color: white;">📥 Importación Excel</a>'
            '<a class="button" href="{}" style="background-color: #3b82f6; color: white;">⚡ Importación Rápida JSON</a>'
            '</div>', 
            url_bg, url_json
        )
    import_background_btn.short_description = "Acciones Masivas"

    def import_background_view(self, request):
        from django.shortcuts import redirect
        from django.urls import reverse
        return redirect(reverse('presupuestos:import_requisiciones_background'))

    def import_json_view(self, request):
        from django.shortcuts import redirect
        from django.urls import reverse
        return redirect(reverse('presupuestos:import_requisiciones_json'))

    def download_template_view(self, request):
        """Genera un archivo Excel con cabeceras y una fila de ejemplo"""
        from .resources import RequisicionResource
        from django.http import HttpResponse
        import tablib

        resource = RequisicionResource()
        headers = resource.get_export_headers()
        dataset = tablib.Dataset(headers=headers)
        
        sample_row = {
            'cr8ca_requisicion': 'REQ-00001-2026',
            'fecha': '2026-02-05',
            'cr8ca_asunto': 'Compra de Material Eléctrico',
            'cr8ca_totalenarticulos': '57168.80',
            'costo': '57168.80',
            'cr8ca_prioridad': '2',
            'cr8ca_id_oc': 'OC-12345',
            'proveedor': 'Proveedor Generico SA',
        }
        
        row_data = [sample_row.get(h, '') for h in headers]
        dataset.append(row_data)
        
        response = HttpResponse(dataset.xlsx, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="formato_importacion_requisiciones.xlsx"'
        return response
    
    class Media:
        css = {
            'all': ('presupuestos/css/requisicion_admin.css',)
        }

    fieldsets = (
        ('Identificación', {
            'fields': ('cr8ca_requisicionid', 'cr8ca_requisicion', 'cr8ca_asunto', 'versionnumber', 'import_background_btn')
        }),
        ('Detalles y Estado', {
            'fields': ('partida', 'item_presupuesto', 'tipo_rutina', 'proveedor', 'cr8ca_motivo', 'cr8ca_comentarios', 'cr8ca_totalenarticulos', 'total_estimado', 'monto_pagado', 'cr8ca_prioridad')
        }),
        ('Flags y Control', {
            'fields': ('cr8ca_ejecutado', 'cr8ca_cerrar', 'cr8ca_cajachica', 'cr8ca_solicituddetabladepago', 'cr8ca_seleccionar', 'statecode', 'statuscode')
        }),
        ('Fechas', {
            'fields': ('fecha', 'cr8ca_fechadegasto', 'createdon', 'modifiedon')
        }),
        ('Lookups Dynamics (IDs)', {
            'classes': ('collapse',),
            'fields': (
                '_ownerid_value',
            )
        }),
    )


@admin.register(ArticuloRequisicion)
class ArticuloRequisicionAdmin(admin.ModelAdmin):
    list_display = ('cr8ca_articulo', 'requisicion', 'material', 'cr8ca_cantidad', 'cr8ca_costoaproximado', 'createdon')
    list_filter = ('createdon', 'cr8ca_tipo', 'material')
    search_fields = ('cr8ca_articulo', 'requisicion__cr8ca_requisicion', 'material__nombre')
    autocomplete_fields = ['requisicion', 'material']
    readonly_fields = ('cr8ca_itemderequisicionid', 'createdon', 'modifiedon')



class ItemSolicitudPagoInline(admin.TabularInline):
    model = ItemSolicitudPago
    extra = 1
    fields = ('requisicion', 'total_req', 'pagado_req', 'monto_solicitado', 'condicion_pago', 'descripcion', 'estatus')
    readonly_fields = ('total_req', 'pagado_req')
    autocomplete_fields = ['requisicion']

    def total_req(self, obj):
        if obj.pk and obj.requisicion:
            return f"{obj.requisicion.total_estimado:,.2f}"
        return "-"
    total_req.short_description = "Total Req."

    def pagado_req(self, obj):
        if obj.pk and obj.requisicion:
            return f"{obj.requisicion.monto_pagado:,.2f}"
        return "-"
    pagado_req.short_description = "Pagado Req."

    def has_add_permission(self, request, obj=None):
        if obj and obj.estado == 'CERRADA':
            return False
        return super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj and obj.estado == 'CERRADA':
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.estado == 'CERRADA':
            return False
        return super().has_delete_permission(request, obj)

@admin.register(SolicitudPago)
class SolicitudPagoAdmin(admin.ModelAdmin):
    change_list_template = 'admin/presupuestos/solicitudpago/change_list.html'
    list_display = ('id', 'descripcion', 'fecha_solicitud', 'usuario_solicitante', 'estado', 'get_total_solicitado', 'get_total_aprobado', 'get_total_pagado')
    list_filter = ('estado', 'fecha_solicitud')
    search_fields = ('descripcion', 'usuario_solicitante__username')
    inlines = [ItemSolicitudPagoInline]
    autocomplete_fields = ['usuario_solicitante']
    readonly_fields = ('get_total_solicitado', 'get_total_aprobado', 'get_total_pagado')

    def total_items(self, obj):
        return obj.items.count()
    total_items.short_description = "# Items"

    def get_total_solicitado(self, obj):
        return f"{obj.total_solicitado:,.2f}"
    get_total_solicitado.short_description = "Monto Solicitado"

    def get_total_aprobado(self, obj):
        return f"{obj.total_aprobado:,.2f}"
    get_total_aprobado.short_description = "Monto Aprobado"

    def get_total_pagado(self, obj):
        return f"{obj.total_pagado:,.2f}"
    get_total_pagado.short_description = "Monto Pagado"

    def get_readonly_fields(self, request, obj=None):
        readonly = super().get_readonly_fields(request, obj)
        if obj and obj.estado == 'CERRADA':
            # Si está cerrada, SOLO los Gerentes pueden editar el campo 'estado'
            # y NADA MÁS. O bien, podemos decir que todo es readonly salvo estado si es gerente.
            # El requerimiento dice: "Una vez que esté en estatus Cerrada, solo los usuarios en el grupo 'Gerentes' Podrán modificar este campo"
            # Asumiremos que el resto de campos quedan bloqueados para todos.
            
            is_gerente = request.user.groups.filter(name='Gerentes').exists()
            if not is_gerente:
                # Bloquear todo para no gerentes
                return [f.name for f in self.model._meta.fields] + list(readonly)
            else:
                # Para gerentes, todo readonly EXCEPTO 'estado' (implícitamente)
                # Obtenemos todos los campos
                all_fields = [f.name for f in self.model._meta.fields]
                # Removemos 'estado' de la lista de readonly
                if 'estado' in all_fields:
                    all_fields.remove('estado')
                return all_fields + list(readonly)
        return readonly

@admin.register(ItemSolicitudPago)
class ItemSolicitudPagoAdmin(admin.ModelAdmin):
    list_display = ('solicitud', 'requisicion', 'total_req', 'pagado_req', 'monto_solicitado', 'condicion_pago', 'estatus', 'creado_en')
    list_filter = ('estatus', 'condicion_pago', 'creado_en')
    search_fields = ('requisicion__cr8ca_requisicion', 'solicitud__descripcion', 'descripcion')
    autocomplete_fields = ['solicitud', 'requisicion']
    readonly_fields = ('total_req', 'pagado_req')
    
    def total_req(self, obj):
        if obj.requisicion:
            return f"{obj.requisicion.total_estimado:,.2f}"
        return "-"
    total_req.short_description = "Total Requisición"

    def pagado_req(self, obj):
        if obj.requisicion:
            return f"{obj.requisicion.monto_pagado:,.2f}"
        return "-"
    pagado_req.short_description = "Pagado Acumulado"


class REPEXItemInline(admin.TabularInline):
    model = REPEXItem
    extra = 1
    fields = ('activo', 'get_estado_activo', 'get_ubicacion', 'costo_original', 'costo_reposicion', 'prioridad', 'fecha_proyectada', 'descripcion')
    readonly_fields = ('get_estado_activo', 'get_ubicacion', 'costo_original')
    autocomplete_fields = ['activo']

    def get_estado_activo(self, obj):
        if obj.activo:
            estado = obj.activo.estado
            colores = {
                'OPERATIVO': '#10B981',
                'MANTENIMIENTO': '#F59E0B',
                'REPARACION': '#F97316',
                'FUERA_SERVICIO': '#EF4444',
                'OBSOLETO': '#6B7280',
            }
            color = colores.get(estado, '#6B7280')
            return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.activo.get_estado_display())
        return "-"
    get_estado_activo.short_description = "Estado Actual"

    def get_ubicacion(self, obj):
        if obj.activo and obj.activo.ubicacion:
            return str(obj.activo.ubicacion)
        return "-"
    get_ubicacion.short_description = "Ubicación"


@admin.register(REPEX)
class REPEXAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'anio', 'estado', 'get_num_items', 'get_costo_total', 'creado_por', 'ver_cronograma_btn')
    list_filter = ('anio', 'estado')
    search_fields = ('nombre', 'descripcion')
    inlines = [REPEXItemInline]
    readonly_fields = ('get_costo_total_detail', 'creado_en', 'actualizado_en')

    def ver_cronograma_btn(self, obj):
        from django.urls import reverse
        if obj.pk:
            url = reverse('presupuestos:cronograma_repex', args=[obj.pk])
            return format_html('<a class="button" href="{}" target="_blank" style="background: #10b981; color: white;">📊 Visualizador Interactivo</a>', url)
        return "-"
    ver_cronograma_btn.short_description = "Cronograma"

    fieldsets = (
        ('Identificación', {
            'fields': ('nombre', 'anio', 'descripcion', 'estado', 'creado_por')
        }),
        ('Resumen de Costos', {
            'fields': ('get_costo_total_detail', 'creado_en', 'actualizado_en')
        }),
    )

    def get_num_items(self, obj):
        return obj.items.count()
    get_num_items.short_description = "# Activos"

    def get_costo_total(self, obj):
        total = obj.costo_total_reposicion or 0
        return format_html('<b style="color: #2563eb;">{}</b>', f"{total:,.2f}")
    get_costo_total.short_description = "Costo Total Reposición"

    def get_costo_total_detail(self, obj):
        if obj.pk:
            total = obj.costo_total_reposicion or 0
            count = obj.items.count()
            return format_html(
                '<div style="font-size: 18px; font-weight: bold; color: #2563eb;">'
                'L {}</div>'
                '<div style="color: #6B7280; font-size: 12px;">{} activos en el plan</div>',
                f"{total:,.2f}", count
            )
        return "Guarde primero para ver el resumen."
    get_costo_total_detail.short_description = "Inversión Total Estimada"


class OrdenCompraArticuloInline(admin.TabularInline):
    model = OrdenCompraArticulo
    extra = 0
    readonly_fields = ['subtotal']
    fields = ['articulo_requisicion', 'descripcion', 'cantidad', 'costo_unitario', 'subtotal']
    autocomplete_fields = ['articulo_requisicion']
    classes = ['collapse']
    verbose_name = "Artículo de OC"
    verbose_name_plural = "Artículos de la OC"

    def has_module_permission(self, request):
        return request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists()

    def has_view_permission(self, request, obj=None):
        return request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists()

    def has_change_permission(self, request, obj=None):
        return request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists()

    def has_add_permission(self, request, obj=None):
        return request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists()

    def has_delete_permission(self, request, obj=None):
        return request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists()


@admin.register(CentroCosto)
class CentroCostoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion', 'activo']
    list_filter = ['activo']
    search_fields = ['nombre']


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = ['numero_oc', 'tipo_documento', 'requisicion_link', 'proveedor', 'total', 'estado', 'fecha_creacion']
    list_filter = ['estado', 'tipo_documento', 'fecha_creacion']
    search_fields = ['numero_oc', 'proveedor__nombre', 'requisicion__cr8ca_requisicion']
    readonly_fields = ['numero_oc', 'subtotal', 'impuestos', 'total', 'fecha_creacion', 'creado_por']
    fieldsets = [
        ('Documento', {'fields': ['tipo_documento', 'numero_oc', 'estado']}),
        ('Referencias', {'fields': ['requisicion', 'proveedor', 'centro_costo']}),
        ('Condiciones de Pago', {'fields': ['anticipo', 'anticipo_porcentaje', 'contraentrega', 'credito', 'credito_dias']}),
        ('Documentación', {'fields': ['doc_factura', 'doc_estimacion', 'doc_respaldo', 'doc_garantia']}),
        ('Montos', {'fields': ['subtotal', 'impuestos', 'total']}),
        ('Fechas', {'fields': ['fecha_creacion', 'fecha_entrega_estimada']}),
        ('Auditoría', {'fields': ['creado_por', 'notas']}),
    ]
    inlines = [OrdenCompraArticuloInline]
    date_hierarchy = 'fecha_creacion'

    def requisicion_link(self, obj):
        from django.urls import reverse
        url = reverse('presupuestos:requisicion_editar', args=[obj.requisicion.pk])
        return format_html('<a href="{}">{}</a>', url, obj.requisicion.cr8ca_requisicion)
    requisicion_link.short_description = "Requisición"
    requisicion_link.admin_order_field = 'requisicion__cr8ca_requisicion'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists():
            return qs
        return qs.none()

    def has_module_permission(self, request):
        return request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists()

    def has_view_permission(self, request, obj=None):
        return request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists()

    def has_change_permission(self, request, obj=None):
        return request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists()

    def has_add_permission(self, request, obj=None):
        return False  # OCs are created via the processing flow, not manually

    def has_delete_permission(self, request, obj=None):
        return request.user.groups.filter(name__in=['Procura', 'PROCURA']).exists()


@admin.register(REPEXItem)
class REPEXItemAdmin(admin.ModelAdmin):
    list_display = ('activo', 'repex', 'prioridad', 'costo_original', 'costo_reposicion', 'fecha_proyectada')
    list_filter = ('prioridad', 'repex')
    search_fields = ('activo__nombre', 'activo__codigo_interno', 'descripcion')
    autocomplete_fields = ['activo', 'repex']


class ItemCotizacionInline(admin.TabularInline):
    model = ItemCotizacion
    extra = 1
    fields = ('item_predefinido', 'descripcion', 'unidad_medida', 'cantidad', 'precio_unitario', 'descuento_porcentaje', 'orden')
    autocomplete_fields = ('item_predefinido',)


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ('numero', 'proyecto', 'disciplina', 'fecha', 'estado', 'total')
    list_filter = ('estado', 'disciplina', 'fecha')
    search_fields = ('numero', 'proyecto__nombre', 'notas')
    autocomplete_fields = ('proyecto', 'disciplina', 'creado_por')
    inlines = [ItemCotizacionInline]


@admin.register(ItemPredefinido)
class ItemPredefinidoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion', 'disciplina', 'unidad_medida', 'precio_unitario', 'moneda', 'activo')
    list_filter = ('disciplina', 'moneda', 'activo')
    search_fields = ('codigo', 'descripcion')
    autocomplete_fields = ('disciplina', 'moneda')


@admin.register(CodigoExoneracion)
class CodigoExoneracionAdmin(ImportExportModelAdmin):
    resource_class = CodigoExoneracionResource
    list_display = ('codigo', 'descripcion', 'nivel', 'dai', 'isc', 'ipc', 'isv', 'activo')
    list_filter = ('activo',)
    search_fields = ('codigo', 'descripcion')
    list_editable = ('dai', 'isc', 'ipc', 'isv', 'activo')
    export_formats = [XLSX, CSV]
    # change_list_template = 'admin/presupuestos/codigoexoneracion/change_list.html'
