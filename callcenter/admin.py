from django.contrib import admin
from .models import SolicitudTicket, GrupoTicket, Institucion, Enlace, TiempoAcordado, TiempoAcordadoTarea

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
    list_display = ('correlativo', 'descripcion_corta', 'get_ubicaciones', 'fecha', 'get_tickets_count')
    list_filter = ('fecha',)
    search_fields = ('correlativo', 'descripcion')
    readonly_fields = ('correlativo', 'fecha')
    inlines = [TicketsInline]
    exclude = ('tickets',)
    
    change_form_template = "admin/callcenter/grupoticket/import_enabled_form.html"
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
        
        if request.method == "POST" and request.FILES.get('excel_file'):
            file = request.FILES['excel_file']
            try:
                # Leer folios del Excel
                df = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)
                
                # Normalizar nombres de columnas
                df.columns = [str(c).lower().strip() for c in df.columns]
                
                folios_raw = []
                if 'folio' in df.columns:
                    folios_raw = df['folio'].dropna().astype(str).tolist()
                else:
                    # Si no hay columna 'folio', tomamos la primera columna
                    folios_raw = df.iloc[:, 0].dropna().astype(str).tolist()

                # Limpiar espacios en los folios
                folios = [f.strip() for f in folios_raw if f.strip()]

                # Buscar los tickets (Usamos __in pero con limpieza previa)
                # NOTA: Folio en la DB podría ser sensible a mayúsculas, usamos __in directamente pero
                # los folios buscados ya no tienen espacios.
                tickets_encontrados = SolicitudTicket.objects.filter(folio__in=folios)
                
                # Si falló la búsqueda exacta, probamos individualmente con limpieza
                if not tickets_encontrados.exists() and folios:
                    from django.db.models import Q
                    query = Q()
                    for f in folios:
                        query |= Q(folio__iexact=f)
                    tickets_encontrados = SolicitudTicket.objects.filter(query)

                # Asociarlos al grupo
                count_antes = grupo.tickets.count()
                ids_seleccionados = list(tickets_encontrados.values_list('id', flat=True))
                grupo.tickets.add(*ids_seleccionados)
                count_despues = grupo.tickets.count()
                
                agregados = count_despues - count_antes
                
                messages.success(request, f"Se procesaron {len(folios)} filas del archivo. Se encontraron {len(ids_seleccionados)} tickets en la base de datos. Se agregaron {agregados} tickets nuevos al grupo.")
                return HttpResponseRedirect("../")
                
            except Exception as e:
                messages.error(request, f"Error al procesar el archivo: {str(e)}")
                return HttpResponseRedirect("../")

        return render(request, "admin/callcenter/grupoticket/importar_modal.html", {"grupo": grupo})

    def get_ubicaciones(self, obj):
        ubicaciones = obj.tickets.filter(ubicacion__isnull=False).values_list('ubicacion__nombre', flat=True).distinct()
        return ", ".join(ubicaciones) if ubicaciones else "-"
    get_ubicaciones.short_description = "Ubicaciones involucradas"

    
    def descripcion_corta(self, obj):
        return obj.descripcion[:50] + "..." if len(obj.descripcion) > 50 else obj.descripcion
    descripcion_corta.short_description = "Descripción"

    def get_tickets_count(self, obj):
        return obj.tickets.count()
    get_tickets_count.short_description = "N° de Tickets"

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
    list_display = ('folio', 'id_solicitud', 'solicitante', 'usuario_responsable', 'get_tiempos_acordados', 'ubicacion', 'servicio', 'area', 'activo', 'deductiva', 'fecha_solicitud')
    list_filter = ('servicio', 'area', 'tipo_solicitud', 'fecha_solicitud', 'ubicacion', ('activo', admin.RelatedOnlyFieldListFilter), ('usuario_responsable', admin.RelatedOnlyFieldListFilter), ('proveedor_deductiva', admin.RelatedOnlyFieldListFilter))
    search_fields = ('folio', 'id_solicitud', 'solicitante', 'solicitud_descripcion', 'diagnostico', 'activo__nombre', 'activo__codigo_interno', 'usuario_responsable__first_name', 'usuario_responsable__last_name', 'usuario_responsable__username')
    autocomplete_fields = ('activo', 'usuario_responsable')
    date_hierarchy = 'fecha_solicitud'
    readonly_fields = ('creado_en', 'actualizado_en')
    actions = ['analizar_con_ia']

    @admin.action(description="Analizar tickets con IA (n8n)")
    def analizar_con_ia(self, request, queryset):
        from .tasks import vectorize_ticket_n8n
        count = 0
        for ticket in queryset:
            vectorize_ticket_n8n.delay(ticket.id)
            count += 1
        self.message_user(request, f"Se han enviado {count} tickets a n8n para análisis semántico.")

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
    
    change_form_template = "admin/callcenter/solicitudticket/change_form.html"

    
    # Organización por Fieldsets (Secciones)
    fieldsets = (
        ('Información General', {
            'fields': (('id_solicitud', 'folio'), ('fecha_solicitud', 'tipo_recepcion'), 'fecha_tipo_recepcion')
        }),
        ('Ubicación y Activos', {
            'fields': (('activo', 'ubicacion'), ('area', 'unidad'), ('servicio', 'subservicio'), ('grupo', 'nivel'))
        }),
        ('Detalle de la Solicitud', {
            'fields': (('solicitante', 'responsable'), 'usuario_responsable', ('tipo_solicitud', 'tiempo_tipo'), 'solicitud_descripcion', 'falla_descripcion', 'falla_clasificacion')
        }),
        ('Seguimiento Técnico', {
            'fields': (('fecha_diagnostico', 'diagnostico'), ('fecha_actividades', 'actividades'), ('fecha_observaciones', 'observaciones'), ('fecha_observaciones_usuario', 'observaciones_usuario'))
        }),
        ('Cierre y Clasificación', {
            'fields': (('fecha_suspension', 'fecha_cierre'), ('clasificacion_falla_final', 'categoria_falla'), 'correo_cierre')
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
    list_select_related = ('activo', 'ubicacion')
    list_per_page = 25

    show_full_result_count = False # Evita el COUNT(*) lento en tablas grandes
    
    def get_queryset(self, request):
        # Seleccionar solo los campos necesarios para la lista unificada
        return super().get_queryset(request).select_related('activo', 'ubicacion').only(
            'id', 'folio', 'id_solicitud', 'solicitante', 'servicio', 'area', 
            'activo__nombre', 'activo__codigo_interno', 'fecha_solicitud', 'tipo_solicitud',
            'ubicacion__nombre'
        )

    def get_urls(self):
        urls = super().get_urls()
        from .views import sync_single_ticket
        custom_urls = [
            path('sync-tickets/', self.admin_site.admin_view(trigger_sync_tickets), name='sync-tickets'),
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
