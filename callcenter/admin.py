from django.contrib import admin
from .models import SolicitudTicket, GrupoTicket, Institucion, Enlace, TiempoAcordado, TiempoAcordadoTarea, FallaTicket

from django.urls import path
from .views import trigger_sync_tickets
from . import views

from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponseRedirect
import pandas as pd # Usaremos pandas para leer Excel rápido
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget
from activos.models import Ubicacion
from core.models import Departamento
from django.contrib.auth.models import User

class TicketsInline(admin.TabularInline):
    model = GrupoTicket.tickets.through
    autocomplete_fields = ('solicitudticket',)
    readonly_fields = ('get_descripcion', 'get_ubicacion')
    verbose_name = "Ticket asociado"
    verbose_name_plural = "Tickets asociados"
    extra = 1

    def get_descripcion(self, obj):
        if obj.solicitudticket:
            return obj.solicitudticket.solicitud_descripcion or obj.solicitudticket.falla_descripcion or "-"
        return "-"
    get_descripcion.short_description = "Descripción del Ticket"

    def get_ubicacion(self, obj):
        if obj.solicitudticket and obj.solicitudticket.ubicacion:
            return obj.solicitudticket.ubicacion.nombre
        return "-"
    get_ubicacion.short_description = "Ubicación"

@admin.register(GrupoTicket)
class GrupoTicketAdmin(admin.ModelAdmin):
    list_display = ('correlativo', 'descripcion_corta', 'get_tickets_count', 'departamento', 'get_estadisticas_generales', 'visualizar_cluster_btn')
    list_filter = ('fecha', 'departamento')
    search_fields = ('correlativo', 'descripcion', 'departamento__nombre')
    readonly_fields = ('correlativo', 'fecha')
    inlines = [TicketsInline]
    exclude = ('tickets',)
    
    change_form_template = "admin/callcenter/grupoticket/change_form.html"
    print(f"DEBUG: Cargando GrupoTicketAdmin con template unico: {change_form_template}")



    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/importar-tickets/', self.admin_site.admin_view(self.importar_tickets_view), name='callcenter_grupoticket_importar'),
            path('plantilla-importacion/', self.admin_site.admin_view(self.exportar_plantilla_view), name='callcenter_grupoticket_plantilla'),
        ]
        return custom_urls + urls

    def exportar_plantilla_view(self, request):
        import tablib
        from django.http import HttpResponse
        
        headers = ['folio']
        # Podemos agregar algunos folios reales como ejemplo si existen
        ejemplos = SolicitudTicket.objects.values_list('folio', flat=True)[:3]
        data = tablib.Dataset(*[(f,) for f in ejemplos], headers=headers)
        
        response = HttpResponse(data.export('xlsx'), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="plantilla_importacion_tickets.xlsx"'
        return response

    def importar_tickets_view(self, request, object_id):
        grupo = self.get_object(request, object_id)
        
        if request.method == "POST":
            folios_raw = []
            
            # 1. Procesar Textarea
            folios_text = request.POST.get('folios_string', '').strip()
            if folios_text:
                import re
                folios_raw.extend(re.split(r'[\s,]+', folios_text))
            
            # 2. Procesar Archivo
            if request.FILES.get('excel_file'):
                file = request.FILES['excel_file']
                try:
                    df = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
                    df.columns = [str(c).lower().strip() for c in df.columns]
                    if 'folio' in df.columns:
                        folios_raw.extend(df['folio'].dropna().astype(str).tolist())
                    else:
                        folios_raw.extend(df.iloc[:, 0].dropna().astype(str).tolist())
                except Exception as e:
                    messages.error(request, f"Error al leer el archivo: {e}")

            # Limpiar y quitar duplicados
            folios = list(set([f.strip() for f in folios_raw if f.strip()]))

            if not folios:
                messages.warning(request, "No se proporcionaron folios válidos.")
                return HttpResponseRedirect("./")

            try:
                # Buscar los tickets
                tickets_encontrados = SolicitudTicket.objects.filter(folio__in=folios)
                ids_to_add = list(tickets_encontrados.values_list('id', flat=True))

                # Si faltan tickets, buscar con iexact
                if len(ids_to_add) < len(folios):
                    found_folios = set(tickets_encontrados.values_list('folio', flat=True))
                    missing_folios = [f for f in folios if f not in found_folios]
                    if missing_folios:
                        from django.db.models import Q
                        query = Q()
                        for f in missing_folios:
                            query |= Q(folio__iexact=f)
                        more_tickets = SolicitudTicket.objects.filter(query)
                        ids_to_add = list(set(ids_to_add + list(more_tickets.values_list('id', flat=True))))

                # Asociarlos al grupo
                count_antes = grupo.tickets.count()
                grupo.tickets.add(*ids_to_add)
                count_despues = grupo.tickets.count()
                
                agregados = count_despues - count_antes
                messages.success(request, f"Se procesaron {len(folios)} folios. Se encontraron {len(ids_to_add)} tickets. Se vincularon {agregados} nuevos.")
                return HttpResponseRedirect("../")
                
            except Exception as e:
                messages.error(request, f"Error al procesar: {str(e)}")
                return HttpResponseRedirect("../")

        return render(request, "admin/callcenter/grupoticket/importar_modal.html", {"grupo": grupo})

    def get_queryset(self, request):
        from django.db.models import Count, Sum, Q
        return super().get_queryset(request).select_related('departamento').annotate(
            tickets_count=Count('tickets', distinct=True),
            tickets_resueltos=Count('tickets', filter=Q(tickets__fecha_cierre__isnull=False), distinct=True),
            deductiva_total=Sum('tickets__deductiva')
        )

    def get_estadisticas_generales(self, obj):
        from django.utils.html import format_html
        
        total = getattr(obj, 'tickets_count', obj.tickets.count())
        if total == 0:
            return format_html(
                '<div style="color:#64748b; font-size:0.85rem; font-style:italic;">'
                '<i class="fas fa-info-circle"></i> Sin tickets asociados'
                '</div>'
            )
            
        resueltos = getattr(obj, 'tickets_resueltos', obj.tickets.filter(fecha_cierre__isnull=False).count())
        pendientes = total - resueltos
        deductiva_total = getattr(obj, 'deductiva_total', None)
        if deductiva_total is None:
            from django.db import models
            deductiva_total = obj.tickets.aggregate(total=models.Sum('deductiva'))['total'] or 0.00
            
        pct_completado = round((resueltos / total) * 100) if total > 0 else 0
        
        # Color del badge de progreso
        if pct_completado == 100:
            progress_color = '#10b981' # Verde esmeralda premium
            progress_bg = '#ecfdf5'
        elif pct_completado >= 50:
            progress_color = '#3b82f6' # Azul royal premium
            progress_bg = '#eff6ff'
        elif pct_completado > 0:
            progress_color = '#f59e0b' # Ámbar premium
            progress_bg = '#fffbeb'
        else:
            progress_color = '#ef4444' # Rojo premium
            progress_bg = '#fef2f2'
            
        deductiva_html = ""
        if deductiva_total and deductiva_total > 0:
            deductiva_html = f'''
            <div style="margin-top: 4px; display: inline-flex; align-items: center; gap: 4px; background: #fff1f2; color: #e11d48; border: 1px solid #ffe4e6; padding: 2px 6px; border-radius: 4px; font-weight: 600; font-size: 0.75rem;">
                <i class="fas fa-dollar-sign"></i> Deductiva: ${deductiva_total:,.2f}
            </div>
            '''
            
        return format_html(
            f'''
            <div style="display: flex; flex-direction: column; gap: 4px; font-family: system-ui, -apple-system, sans-serif; font-size: 0.85rem; min-width: 180px;">
                <div style="display: flex; align-items: center; gap: 6px;">
                    <span style="background: {progress_bg}; color: {progress_color}; border: 1px solid {progress_color}40; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.75rem; display: inline-flex; align-items: center; gap: 3px;">
                        <i class="fas fa-tasks"></i> {pct_completado}%
                    </span>
                    <span style="color: #475569; font-weight: 500;">
                        {resueltos} de {total} resueltos
                    </span>
                </div>
                <div style="display: flex; gap: 8px; font-size: 0.75rem; color: #64748b;">
                    <span><i class="fas fa-check-circle" style="color: #10b981;"></i> Resueltos: <strong>{resueltos}</strong></span>
                    <span><i class="fas fa-exclamation-circle" style="color: #ef4444;"></i> Pendientes: <strong style="color: {"#ef4444" if pendientes > 0 else "#64748b"};">{pendientes}</strong></span>
                </div>
                {deductiva_html}
            </div>
            '''
        )
    get_estadisticas_generales.short_description = "Estadísticas Generales"

    def descripcion_corta(self, obj):
        return obj.descripcion[:50] + "..." if len(obj.descripcion) > 50 else obj.descripcion
    descripcion_corta.short_description = "Descripción"

    def get_tickets_count(self, obj):
        return getattr(obj, 'tickets_count', obj.tickets.count())
    get_tickets_count.short_description = "N° de Tickets"

    def visualizar_cluster_btn(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('callcenter:cluster_tickets', args=[obj.id])
        return format_html(
            f'''
            <a href="{url}" target="_blank" class="btn btn-sm btn-primary" 
               style="background: linear-gradient(135deg, #3b82f6, #1d4ed8); 
                      color: white; 
                      border: none; 
                      padding: 4px 10px; 
                      border-radius: 4px; 
                      font-weight: 600; 
                      font-size: 0.75rem; 
                      display: inline-flex; 
                      align-items: center; 
                      gap: 4px; 
                      text-decoration: none;
                      box-shadow: 0 2px 4px rgba(29, 78, 216, 0.15);
                      transition: all 0.2s ease;">
                <i class="fas fa-eye" style="font-size: 0.8rem;"></i> Visualizar
            </a>
            '''
        )
    visualizar_cluster_btn.short_description = "Acción"

from .models import SolicitudTicket, GrupoTicket, EvidenciaTicket
from django.utils.html import format_html

class EvidenciasInline(admin.TabularInline):
    model = EvidenciaTicket
    extra = 1
    fields = ('archivo', 'descripcion', 'ver_archivo')
    readonly_fields = ('ver_archivo',)

    def ver_archivo(self, obj):
        if obj.archivo:
            if obj.archivo.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                return format_html('<a href="{0}" target="_blank"><img src="{0}" style="max-height: 50px; border-radius: 5px;" /></a>', obj.archivo.url)
            return format_html('<a href="{0}" target="_blank" class="btn btn-xs btn-info"><i class="fas fa-download"></i> Ver Archivo</a>', obj.archivo.url)
        return "-"
    ver_archivo.short_description = "Vista Previa"

@admin.register(SolicitudTicket)
class SolicitudTicketAdmin(admin.ModelAdmin):
    list_display = ('folio', 'es_interno', 'solicitud_adicional', 'id_solicitud', 'solicitante', 'falla_reportada', 'diagnostico_reportado', 'usuario_responsable', 'robot_estatus', 'get_tiempos_acordados', 'ubicacion', 'servicio', 'area', 'activo', 'deductiva', 'fecha_solicitud')
    list_filter = ('robot_estatus', 'es_interno', 'servicio', 'area', 'tipo_solicitud', 'falla_reportada', 'diagnostico_reportado', 'falla_clasificacion', 'categoria_falla', 'fecha_solicitud', 'ubicacion', ('activo', admin.RelatedOnlyFieldListFilter), ('usuario_responsable', admin.RelatedOnlyFieldListFilter), ('proveedor_deductiva', admin.RelatedOnlyFieldListFilter))
    search_fields = ('folio', 'id_solicitud', 'solicitante', 'solicitud_descripcion', 'falla_descripcion', 'falla_reportada__nombre', 'diagnostico_reportado__nombre', 'diagnostico', 'activo__nombre', 'activo__codigo_interno', 'usuario_responsable__first_name', 'usuario_responsable__last_name', 'usuario_responsable__username')
    autocomplete_fields = ('activo', 'usuario_responsable')
    date_hierarchy = 'fecha_solicitud'
    readonly_fields = ('creado_en', 'actualizado_en', 'robot_estatus', 'robot_log')
    actions = ['analizar_con_ia', 'exportar_a_excel']

    @admin.action(description="Analizar tickets con IA (n8n)")
    def analizar_con_ia(self, request, queryset):
        from .tasks import vectorize_ticket_n8n
        count = 0
        for ticket in queryset:
            vectorize_ticket_n8n.delay(ticket.id)
            count += 1
        self.message_user(request, f"Se han enviado {count} tickets a n8n para análisis semántico.")

    @admin.action(description="Exportar tickets seleccionados a Excel (Masivo)")
    def exportar_a_excel(self, request, queryset):
        import tablib
        from django.http import HttpResponse
        
        headers = [
            'ID', 'Folio', 'ID Solicitud', 'Solicitante', 'Asignado', 'Usuario Responsable', 
            'Ubicación Física', 'Servicio', 'Área', 'Activo Relacionado', 
            'Serie Activo', 'Deductiva (USD)', 'Fecha Solicitud', 'Fecha Cierre', 
            'Falla Reportada', 'Diagnóstico Catálogo', 'Diagnóstico', 'Actividades', 'Observaciones', 'Estado'
        ]
        
        data = tablib.Dataset(headers=headers)
        
        # Obtenemos un QuerySet limpio ignorando el .only() del changelist original para evitar FieldError
        from .models import SolicitudTicket
        clean_queryset = SolicitudTicket.objects.filter(id__in=queryset.values('id')).select_related(
            'ubicacion', 'usuario_responsable', 'activo', 'falla_reportada', 'diagnostico_reportado'
        )
        
        for t in clean_queryset:
            data.append((
                t.id,
                t.folio or '',
                t.id_solicitud or '',
                t.solicitante or '',
                t.responsable or '',
                t.usuario_responsable.get_full_name() if t.usuario_responsable else '',
                t.ubicacion.nombre if t.ubicacion else '',
                t.servicio or '',
                t.area or '',
                t.activo.nombre if t.activo else '',
                t.activo.serie if t.activo else '',
                str(t.deductiva) if t.deductiva else '0.00',
                t.fecha_solicitud.strftime("%Y-%m-%d %H:%M") if t.fecha_solicitud else '',
                t.fecha_cierre.strftime("%Y-%m-%d %H:%M") if t.fecha_cierre else '',
                t.falla_reportada.nombre if t.falla_reportada else '',
                t.diagnostico_reportado.nombre if t.diagnostico_reportado else '',
                t.diagnostico or '',
                t.actividades or '',
                t.observaciones or '',
                'Cerrado' if t.fecha_cierre else 'Abierto'
            ))
            
        response = HttpResponse(
            data.export('xlsx'), 
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="Exportacion_Masiva_Tickets.xlsx"'
        return response

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if not request.user.is_superuser:
            ro.append('correo_cierre')
        return ro
    inlines = [EvidenciasInline]
    
    def get_tiempos_acordados(self, obj):
        count = obj.tiempos_acordados.count()
        if count > 0:
            return format_html('<span class="badge badge-info" style="background:#0070f2; color:white;"><i class="fas fa-clock"></i> {} Acordado(s)</span>', count)
        return "-"
    get_tiempos_acordados.short_description = "T. Acordado"
    
    def falla_descripcion_corta(self, obj):
        if not obj.falla_descripcion:
            return "-"
        return obj.falla_descripcion[:50] + "..." if len(obj.falla_descripcion) > 50 else obj.falla_descripcion
    falla_descripcion_corta.short_description = "Desc. Falla"
    
    change_form_template = "admin/callcenter/solicitudticket/change_form.html"

    
    # Organización por Fieldsets (Secciones)
    fieldsets = (
        ('Información General', {
            'fields': (('id_solicitud', 'folio', 'es_interno', 'solicitud_adicional'), ('fecha_solicitud', 'tipo_recepcion'), 'fecha_tipo_recepcion')
        }),
        ('Ubicación y Activos', {
            'fields': (('activo', 'ubicacion'), ('area', 'unidad'), ('servicio', 'subservicio'), ('grupo', 'nivel'))
        }),
        ('Detalle de la Solicitud', {
            'fields': (('solicitante', 'responsable'), 'usuario_responsable', ('tipo_solicitud', 'tiempo_tipo'), 'solicitud_descripcion', 'falla_descripcion', 'falla_clasificacion', 'falla_reportada')
        }),
        ('Seguimiento Técnico', {
            'fields': (('fecha_diagnostico', 'diagnostico_reportado', 'diagnostico'), ('fecha_actividades', 'actividades'), ('fecha_observaciones', 'observaciones'), ('fecha_observaciones_usuario', 'observaciones_usuario'))
        }),
        ('Cierre y Clasificación', {
            'fields': (('fecha_suspension', 'fecha_cierre'), ('clasificacion_falla_final', 'categoria_falla'), 'correo_cierre')
        }),
        ('Automatización del Robot (Playwright)', {
            'fields': ('robot_estatus', 'robot_log')
        }),
        ('Información Financiera / Deductivas', {
            'fields': (('deductiva', 'proveedor_deductiva'),)
        }),
        ('Auditoría', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )


    # Optimización de Performance
    list_select_related = ('activo', 'ubicacion', 'falla_reportada', 'diagnostico_reportado')
    list_per_page = 25

    show_full_result_count = False # Evita el COUNT(*) lento en tablas grandes
    
    def get_queryset(self, request):
        # Seleccionar solo los campos necesarios para la lista unificada
        return super().get_queryset(request).select_related('activo', 'ubicacion', 'falla_reportada', 'diagnostico_reportado').only(
            'id', 'folio', 'es_interno', 'solicitud_adicional', 'id_solicitud', 'solicitante', 'servicio', 'area', 
            'falla_descripcion', 'falla_reportada', 'diagnostico_reportado',
            'activo__nombre', 'activo__codigo_interno', 'fecha_solicitud', 'tipo_solicitud',
            'ubicacion__nombre', 'robot_estatus'
        )

    def get_urls(self):
        urls = super().get_urls()
        from .views import sync_single_ticket
        custom_urls = [
            path('sync-tickets/', self.admin_site.admin_view(trigger_sync_tickets), name='sync-tickets'),
            path('sync-by-folios/', self.admin_site.admin_view(views.trigger_sync_by_folios), name='sync-by-folios'),
            path('<int:ticket_id>/sync-singular/', self.admin_site.admin_view(sync_single_ticket), name='sync-singular'),
            path('<int:ticket_id>/enviar-power-automate/', self.admin_site.admin_view(views.send_ticket_to_power_automate_view), name='enviar_power_automate'),
            path('<int:ticket_id>/cierre-visual/', self.admin_site.admin_view(views.ticket_cierre_visual_view), name='cierre_visual'),
        ]
        return custom_urls + urls
# --- Nuevos Modelos de Tiempo Acordado ---

class TiempoAcordadoTareaInline(admin.TabularInline):
    model = TiempoAcordadoTarea
    extra = 3
    fields = ('descripcion', 'fecha_inicio', 'fecha_fin', 'completada')

class EnlaceInline(admin.TabularInline):
    model = Enlace
    extra = 1
    autocomplete_fields = ('ubicacion',)

# --- Import Export Resources ---

class InstitucionResource(resources.ModelResource):
    ubicaciones = fields.Field(
        column_name='ubicaciones',
        attribute='ubicaciones',
        widget=ManyToManyWidget(Ubicacion, field='nombre', separator='|')
    )
    class Meta:
        model = Institucion
        fields = ('id', 'nombre', 'acronimo', 'ubicaciones')
        export_order = ('id', 'nombre', 'acronimo', 'ubicaciones')

class EnlaceResource(resources.ModelResource):
    institucion = fields.Field(
        column_name='institucion',
        attribute='institucion',
        widget=ForeignKeyWidget(Institucion, 'nombre')
    )
    ubicacion = fields.Field(
        column_name='ubicacion',
        attribute='ubicacion',
        widget=ForeignKeyWidget(Ubicacion, 'nombre')
    )

    class Meta:
        model = Enlace
        fields = ('id', 'nombre', 'institucion', 'email', 'telefono', 'ubicacion')
        export_order = ('id', 'nombre', 'institucion', 'email', 'telefono', 'ubicacion')

@admin.register(Institucion)
class InstitucionAdmin(ImportExportModelAdmin):
    resource_class = InstitucionResource
    list_display = ('nombre', 'acronimo', 'get_ubicaciones_count')
    filter_horizontal = ('ubicaciones',)
    search_fields = ('nombre', 'acronimo')
    inlines = [EnlaceInline]

    def get_ubicaciones_count(self, obj):
        return obj.ubicaciones.count()
    get_ubicaciones_count.short_description = "N° Ubicaciones"

@admin.register(Enlace)
class EnlaceAdmin(ImportExportModelAdmin):
    resource_class = EnlaceResource
    list_display = ('nombre', 'institucion', 'email', 'telefono', 'ubicacion')
    list_filter = ('institucion', 'ubicacion')
    search_fields = ('nombre', 'email', 'telefono', 'institucion__nombre')
    autocomplete_fields = ('ubicacion', 'institucion')

@admin.register(TiempoAcordado)
class TiempoAcordadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_folio', 'enlace', 'institucion', 'estatus', 'fecha_solucion_final', 'departamento')
    list_filter = ('estatus', 'departamento', 'institucion', 'creado_en')
    search_fields = ('ticket__folio', 'ticket__id_solicitud', 'enlace__nombre', 'motivo_extension', 'institucion__nombre')
    autocomplete_fields = ('ticket', 'enlace', 'ubicacion', 'institucion')
    inlines = [TiempoAcordadoTareaInline]
    readonly_fields = ('usuario_creador', 'departamento', 'creado_en', 'actualizado_en')
    
    fieldsets = (
        ('Vinculación', {
            'fields': (('ticket', 'enlace'), ('institucion', 'ubicacion'))
        }),
        ('Detalles del Acuerdo', {
            'fields': ('motivo_extension', 'solucion_provisional', 'fecha_solucion_final', 'estatus', 'observaciones')
        }),
        ('Auditoría', {
            'fields': (('usuario_creador', 'departamento'), ('creado_en', 'actualizado_en')),
            'classes': ('collapse',),
        }),
    )

    def get_folio(self, obj):
        return obj.ticket.folio or obj.ticket.id_solicitud
    get_folio.short_description = "Folio Ticket"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.usuario_creador = request.user
            if hasattr(request.user, 'perfil') and request.user.perfil.departamento:
                obj.departamento = request.user.perfil.departamento
        super().save_model(request, obj, form, change)

    class Media:
        js = ('callcenter/js/tiempo_acordado_admin.js',)

# --- Registros Manuales Pendientes ---
@admin.register(TiempoAcordadoTarea)
class TiempoAcordadoTareaAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'tiempo_acordado', 'fecha_inicio', 'fecha_fin', 'completada')
    list_filter = ('completada', 'fecha_inicio')


# --- ADMINISTRACIÓN DE CRONOGRAMAS PREDEFINIDOS (PLANTILLAS) ---

from .models import CronogramaPredefinido, CronogramaItemPredefinido

class CronogramaItemPredefinidoInline(admin.TabularInline):
    model = CronogramaItemPredefinido
    extra = 5
    fields = ('numero', 'descripcion', 'duracion_dias', 'predecesores')
    autocomplete_fields = ('predecesores',)
    sortable_field_name = "numero"

@admin.register(CronogramaPredefinido)
class CronogramaPredefinidoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'departamento', 'get_items_count')
    list_filter = ('departamento',)
    search_fields = ('nombre',)
    inlines = [CronogramaItemPredefinidoInline]

    def get_items_count(self, obj):
        return obj.items.count()
    get_items_count.short_description = "N° de Items"

@admin.register(CronogramaItemPredefinido)
class CronogramaItemPredefinidoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'descripcion', 'cronograma', 'duracion_dias')
    list_filter = ('cronograma', 'duracion_dias')
    search_fields = ('descripcion', 'cronograma__nombre')
    autocomplete_fields = ('cronograma', 'predecesores')


class FallaTicketResource(resources.ModelResource):
    parent = fields.Field(
        column_name='parent',
        attribute='parent',
        widget=ForeignKeyWidget(FallaTicket, field='nombre')
    )
    departamento_responsable = fields.Field(
        column_name='departamento_responsable',
        attribute='departamento_responsable',
        widget=ForeignKeyWidget(Departamento, 'nombre')
    )
    usuario_responsable = fields.Field(
        column_name='usuario_responsable',
        attribute='usuario_responsable',
        widget=ForeignKeyWidget(User, 'username')
    )

    class Meta:
        model = FallaTicket
        fields = ('id', 'nombre', 'parent', 'descripcion', 'departamento_responsable', 'usuario_responsable')
        export_order = ('id', 'nombre', 'parent', 'departamento_responsable', 'usuario_responsable', 'descripcion')
        import_id_fields = ('id',)
        skip_unchanged = True
        report_skipped = True

    def get_instance(self, instance_loader, row):
        """Intenta buscar por ID o por nombre para actualizaciones."""
        obj_id = row.get('id')
        if obj_id:
            try:
                return self.get_queryset().get(id=obj_id)
            except FallaTicket.DoesNotExist:
                return None
        
        nombre = row.get('nombre')
        if nombre:
            try:
                return self.get_queryset().get(nombre=nombre)
            except FallaTicket.DoesNotExist:
                return None
        return None

from .models import DiagnosticoTicket

class DiagnosticoTicketInline(admin.TabularInline):
    model = DiagnosticoTicket
    extra = 1
    fields = ('nombre', 'descripcion')

@admin.register(FallaTicket)
class FallaTicketAdmin(ImportExportModelAdmin):
    resource_class = FallaTicketResource
    list_display = ('nombre', 'parent', 'departamento_responsable', 'usuario_responsable', 'get_tickets_count')
    list_filter = ('parent', 'departamento_responsable', 'usuario_responsable')
    search_fields = ('nombre', 'descripcion')
    autocomplete_fields = ('parent', 'usuario_responsable')
    inlines = [DiagnosticoTicketInline]
    
    change_list_template = "admin/callcenter/fallaticket/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('importar-background/', self.admin_site.admin_view(views.import_fallatickets_process), name='callcenter_fallaticket_import_background'),
        ]
        return custom_urls + urls

    def get_tickets_count(self, obj):
        return obj.tickets.count()
    get_tickets_count.short_description = "Tickets vinculados"

class DiagnosticoTicketResource(resources.ModelResource):
    falla = fields.Field(
        column_name='falla',
        attribute='falla',
        widget=ForeignKeyWidget(FallaTicket, field='nombre')
    )

    class Meta:
        model = DiagnosticoTicket
        fields = ('id', 'nombre', 'falla', 'descripcion')
        export_order = ('id', 'nombre', 'falla', 'descripcion')
        import_id_fields = ('id',)
        skip_unchanged = True
        report_skipped = True

    def get_instance(self, instance_loader, row):
        """Intenta buscar por ID o por nombre y falla para actualizaciones."""
        obj_id = row.get('id')
        if obj_id:
            try:
                return self.get_queryset().get(id=obj_id)
            except DiagnosticoTicket.DoesNotExist:
                return None
        
        nombre = row.get('nombre')
        if nombre:
            try:
                falla_nombre = row.get('falla')
                if falla_nombre:
                    return self.get_queryset().get(nombre=nombre, falla__nombre=falla_nombre)
                return self.get_queryset().get(nombre=nombre)
            except (DiagnosticoTicket.DoesNotExist, DiagnosticoTicket.MultipleObjectsReturned):
                return None
        return None


@admin.register(DiagnosticoTicket)
class DiagnosticoTicketAdmin(ImportExportModelAdmin):
    resource_class = DiagnosticoTicketResource
    list_display = ('nombre', 'falla', 'descripcion')
    list_filter = ('falla',)
    search_fields = ('nombre', 'descripcion', 'falla__nombre')
    autocomplete_fields = ('falla',)
    
    change_list_template = "admin/callcenter/diagnosticoticket/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('importar-background/', self.admin_site.admin_view(views.import_diagnosticos_process), name='callcenter_diagnosticoticket_import_background'),
        ]
        return custom_urls + urls
