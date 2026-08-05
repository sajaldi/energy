from django.contrib import admin
from django.utils.safestring import mark_safe
from import_export import resources, fields, widgets
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin
from django.urls import path, reverse
from django.utils.html import format_html
from django.db import connection
import pandas as pd
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from django.db import transaction

from .models import (
    Consumo, InterfaceConsumo, Medidor, PuntoMedicion, Equipo,
    CaracteristicaMedicion, CategoriaPuntoMedicion, DocumentoMedicion, RangoMedicion, TipoMedidor, UnidadMedida, VistaConsumoDiferencia,
    Servicio, KPI, PerfilUsuario, ConfiguracionUI, Departamento, ElementoApp,
    AdminNavMenu, AdminNavColumn, AdminNavItem,
)
from mantenimiento.models import PuestoTrabajo

@admin.register(ConfiguracionUI)
class ConfiguracionUIAdmin(admin.ModelAdmin):
    fieldsets = (
        ('General', {
            'fields': ('titulo_proyecto', 'color_primario', 'color_secundario')
        }),
        ('Matriz de Mantenimiento', {
            'fields': ('matriz_header_bg', 'matriz_header_text', 'matriz_border_color', 'matriz_hover_row', 'matriz_hover_cell')
        }),
        ('Órdenes de Trabajo', {
            'fields': ('orden_preventiva_bg', 'orden_correctiva_bg', 'orden_texto')
        }),
    )

    def has_add_permission(self, request):
        # Only allow adding if there is no config yet
        return not ConfiguracionUI.objects.exists()

from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    fk_name = 'usuario'
    can_delete = False
    verbose_name_plural = 'Perfil de Usuario / Configuración'
    fields = ('telefono', 'puesto', 'departamento', 'responsable', 'ubicacion_defecto', 'visto_tutorial', 'invitation_status', 'nav_config')
    raw_id_fields = ('ubicacion_defecto',)
    autocomplete_fields = ('responsable', 'departamento', 'puesto')

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'puesto', 'departamento', 'telefono', 'visto_tutorial', 'ubicacion_defecto')
    list_filter = ('departamento', 'puesto', 'visto_tutorial', 'ubicacion_defecto')
    search_fields = ('usuario__username', 'usuario__email', 'departamento__nombre', 'puesto__nombre')
    raw_id_fields = ('ubicacion_defecto',)
    autocomplete_fields = ('departamento', 'puesto')

# Unregister standard User and Register with Profile Inline
admin.site.unregister(User)
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (PerfilUsuarioInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_nombre_completo', 'is_staff')
    readonly_fields = BaseUserAdmin.readonly_fields + ('boton_invitacion', 'boton_impersonar')

    # Insertar los botones en el primer fieldset (Personal info) o crear uno nuevo
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj:  # solo en edición, no en creación
            extra_fieldsets = []
            if request.user.is_superuser:
                extra_fieldsets.append(
                    ('Inpersonación', {
                        'fields': ('boton_impersonar',),
                        'description': 'Actúa como este usuario para ver el sistema desde su perspectiva.',
                    }),
                )
            extra_fieldsets.append(
                ('Invitación', {
                    'fields': ('boton_invitacion',),
                    'description': 'Envía o reenvía el correo de activación de cuenta.',
                }),
            )
            return fieldsets + tuple(extra_fieldsets)
        return fieldsets

    def get_nombre_completo(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()
    get_nombre_completo.short_description = 'Nombre Completo'

    def boton_impersonar(self, obj):
        if not obj.pk:
            return mark_safe('<span style="color:#94a3b8">Guarda el usuario primero.</span>')
        if obj.is_superuser:
            return mark_safe('<span style="color:#94a3b8">—</span>')
        url = reverse('core:impersonate_start', args=[obj.pk])
        return mark_safe(
            f'<a href="{url}" class="button" style="background:#8b5cf6;border-color:#7c3aed;color:#fff;'
            f'padding:8px 18px;border-radius:6px;font-weight:700;text-decoration:none;font-size:13px;" '
            f'onclick="return confirm(\'¿Impersonar a {obj.get_full_name() or obj.username}?\\n\\nPodrás ver el sistema como este usuario.\')">'
            f'&#128100; Impersonar</a>'
        )
    boton_impersonar.short_description = 'Impersonar'

    def boton_invitacion(self, obj):
        if not obj.pk:
            return mark_safe('<span style="color:#94a3b8">Guarda el usuario primero.</span>')
        url = f'/admin/auth/user/{obj.pk}/send-invitation/'
        perfil = getattr(obj, 'perfil', None)
        status = getattr(perfil, 'invitation_status', 'active') if perfil else 'active'
        is_pending = (status == 'pending') or (not obj.is_active)
        if is_pending:
            label = '&#128231; Reenviar Invitación'
            style = 'background:#f59e0b;border-color:#d97706;color:#fff;'
            hint = '<span style="font-size:11px;color:#64748b;display:block;margin-top:6px;">El usuario tiene una invitación pendiente. Se generará un nuevo token.</span>'
        else:
            label = '&#128231; Enviar Invitación'
            style = 'background:#2563eb;border-color:#1d4ed8;color:#fff;'
            hint = '<span style="font-size:11px;color:#64748b;display:block;margin-top:6px;">Se enviará un correo con el enlace de activación.</span>'
        return mark_safe(
            f'<a href="{url}" class="button" style="{style}padding:8px 18px;'
            f'border-radius:6px;font-weight:700;text-decoration:none;font-size:13px;">'
            f'{label}</a>{hint}'
        )
    boton_invitacion.short_description = 'Invitación de Acceso'

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path('<int:user_id>/send-invitation/',
                 self.admin_site.admin_view(self.send_invitation_view),
                 name='auth_user_send_invitation'),
        ]
        return custom + urls

    def send_invitation_view(self, request, user_id):
        from django.shortcuts import redirect
        from django.contrib import messages
        from invitaciones.services import InvitationService, TokenService, LinkBuilder, PowerAutomateInvitationService
        from invitaciones.exceptions import InvalidResendTarget, PowerAutomateDispatchError, ConfigurationError

        user_obj = User.objects.filter(pk=user_id).first()
        if not user_obj:
            messages.error(request, 'Usuario no encontrado.')
            return redirect('../../../')

        try:
            token_svc    = TokenService()
            link_builder = LinkBuilder()
            inv_token    = token_svc.generate_token(user_obj)
            inv_link     = link_builder.build(inv_token.token)

            # Llamada directa (síncrona) a Power Automate — sin Celery
            PowerAutomateInvitationService().dispatch(
                email           = user_obj.email,
                username        = user_obj.get_full_name() or user_obj.username,
                invitation_link = inv_link,
            )

            # Actualizar estado del perfil
            perfil = getattr(user_obj, 'perfil', None)
            if perfil and perfil.invitation_status != 'pending':
                perfil.invitation_status = 'pending'
                perfil.save(update_fields=['invitation_status'])

            messages.success(request, f'✅ Invitación enviada a {user_obj.email}.')

        except (PowerAutomateDispatchError, ConfigurationError) as e:
            messages.error(request, f'Error al enviar el correo: {e}')
        except Exception as e:
            messages.error(request, f'Error inesperado: {e}')

        return redirect(f'/admin/auth/user/{user_id}/change/')


from . import views

# ==============================================================================
# FUNCIÓN AUXILIAR PARA GENERAR EL GRÁFICO (la ponemos al principio)
# ==============================================================================
def generar_grafico_ultimos_6_meses(medidor):
    hoy = datetime.now()
    fecha_inicio = hoy - timedelta(days=180)
    tipo_normalizado = (medidor.tipo or "").strip().upper()

    query_mensual = ""
    if tipo_normalizado == 'PUNTUAL':
        query_mensual = f"""
            SELECT TO_CHAR(fecha, 'YYYY-MM') AS mes, SUM(consumo) AS consumo_mensual
            FROM core_consumo WHERE medidor_id = {medidor.id} AND fecha >= '{fecha_inicio.strftime('%Y-%m-%d')}'
            GROUP BY TO_CHAR(fecha, 'YYYY-MM') ORDER BY mes DESC LIMIT 6;
        """
    else:
        query_mensual = f"""
            SELECT mes, (consumo_actual - consumo_anterior) AS consumo_mensual FROM (
                SELECT TO_CHAR(fecha_final_mes, 'YYYY-MM') AS mes, consumo_final_mes AS consumo_actual,
                       LAG(consumo_final_mes) OVER (PARTITION BY medidor_id ORDER BY fecha_final_mes) AS consumo_anterior
                FROM (
                    SELECT medidor_id, MAX(fecha) AS fecha_final_mes,
                           (SELECT consumo FROM core_consumo WHERE medidor_id = c.medidor_id AND fecha = MAX(c.fecha)) AS consumo_final_mes
                    FROM core_consumo c WHERE medidor_id = {medidor.id} AND fecha >= '{fecha_inicio.strftime('%Y-%m-%d')}'
                    GROUP BY medidor_id, TO_CHAR(fecha, 'YYYY-MM')
                ) AS lecturas
            ) AS calculo WHERE consumo_anterior IS NOT NULL ORDER BY mes DESC LIMIT 6;
        """
    try:
        df = pd.read_sql(query_mensual, connection)
        if df.empty: return None

        df = df.sort_values('mes').reset_index(drop=True)
        fig, ax = plt.subplots(figsize=(10, 4))
        bars = ax.bar(df['mes'], df['consumo_mensual'])
        unidad_simbolo = medidor.unidad.simbolo if medidor.unidad and medidor.unidad.simbolo else 'unidades'
        ax.set_ylabel(f'Consumo ({unidad_simbolo})')
        ax.set_title('Consumo de los Últimos 6 Meses')
        ax.bar_label(bars, fmt=lambda x: f'{x:,.0f}'.replace(',', '.'), padding=3)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        plt.close(fig)
        return img_base64
    except Exception as e:
        print(f"Error generando gráfico para medidor {medidor.id}: {e}")
        return None

# ==============================================================================
# CLASES DE RECURSOS PARA IMPORT/EXPORT (sin cambios)
# ==============================================================================
class ConsumoResource(resources.ModelResource):
    medidor = fields.Field(
        column_name='medidor',
        attribute='medidor',
        widget=ForeignKeyWidget(Medidor, field='nombre')
    )

    class Meta:
        model = Consumo
        fields = ('id', 'fecha', 'consumo', 'medidor')
        export_order = ('id', 'fecha', 'medidor', 'consumo')
        skip_unchanged = True
        report_skipped = True
        use_bulk = True
        batch_size = 1000

    def before_import(self, dataset, *args, **kwargs):
        """Precarga medidores para evitar N+1 queries"""
        self.medidor_map = {m.nombre: m.id for m in Medidor.objects.all().values('id', 'nombre')}

    def before_import_row(self, row, **kwargs):
        """Opcional: validaciones o transformaciones rápidas"""
        pass

class FixedImportExportAdmin(ImportExportModelAdmin):
    # ... (tu código de FixedImportExportAdmin sin cambios) ...
    pass

# ==============================================================================
# CLASES DE ADMINISTRACIÓN
# ==============================================================================

@admin.register(Consumo)
class ConsumoAdmin(FixedImportExportAdmin):
    resource_class = ConsumoResource # Vinculamos el resource
    # Mantenemos el resto de tu configuración
    list_display = ['id','fecha', 'consumo', 'medidor']
    list_filter = ['fecha', 'medidor']
    list_select_related = ['medidor']
    raw_id_fields = ['medidor']
    date_hierarchy = 'fecha'
    list_per_page = 10
    search_fields = ['id','medidor__nombre', 'consumo']
    
    # El resto de tus métodos para ConsumoAdmin (get_urls, changelist_view, etc.)
    # ... (van aquí si los tenías, si no, puedes omitirlos)

@admin.register(TipoMedidor)
class TipoMedidorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion']
    search_fields = ['nombre']
    list_filter = ['nombre']
    ordering = ['nombre']
    list_per_page = 10
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('medidores')

class MedidorInline(admin.TabularInline):
    model = Medidor
    fk_name = 'medidor_padre'
    extra = 0
    fields = ['nombre', 'tipo', 'tipo_medidor']
    readonly_fields = ['nombre', 'tipo', 'tipo_medidor']
    show_change_link = True
    ordering = ['nombre']
    

class ConsumoInline(admin.TabularInline):
    model = Consumo
    extra = 0
    fields = ['fecha', 'consumo']
    readonly_fields = ['fecha', 'consumo']
    show_change_link = True
    # Dejamos el ordering aquí para que el admin lo conozca
    ordering = ['-fecha'] 
    
    # --- SOLUCIÓN DEFINITIVA A PRUEBA DE FILTROS ---
    def get_queryset(self, request, obj=None):
        # 1. Obtenemos el queryset base, que ya está filtrado por el medidor padre.
        qs = super().get_queryset(request)

        # 2. Si no estamos en la página de un objeto existente, no mostramos nada.
        if not obj:
            return qs.none()

        # 3. Obtenemos los IDs de los 10 registros más recientes que queremos mostrar.
        #    'values_list' es muy eficiente, solo trae los IDs de la base de datos.
        #    'flat=True' nos da una lista simple de IDs: [101, 95, 88, ...]
        latest_consumo_ids = qs.order_by('-fecha')[:10].values_list('id', flat=True)

        # 4. Filtramos el queryset original por esta lista de IDs.
        #    Esto devuelve un QuerySet PEREZOSO (no evaluado) y filtrable, 
        #    sobre el que el admin puede añadir más filtros si lo necesita
        #    sin causar el error de "slice".
        return qs.filter(pk__in=list(latest_consumo_ids))

    def has_add_permission(self, request, obj=None):
        return False
    
    
@admin.register(Medidor)
class MedidorAdmin(admin.ModelAdmin):
    list_display = ['id','nombre', 'tipo', 'tipo_medidor', 'medidor_padre','unidad']
    search_fields = ['nombre']
    list_filter = ['tipo', 'tipo_medidor']
    ordering = ['nombre']
    list_per_page = 10
    inlines = [MedidorInline, ConsumoInline] # Agregamos ambos inlines

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tipo_medidor', 'medidor_padre', 'unidad')

    # --- MÉTODO SOBRESCRITO PARA AÑADIR EL GRÁFICO ---
    def change_view(self, request, object_id, form_url='', extra_context=None):
        medidor = self.get_object(request, object_id)
        extra_context = extra_context or {}
        if medidor:
            extra_context['grafico_consumo'] = generar_grafico_ultimos_6_meses(medidor)
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context,
        )


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'simbolo', 'descripcion']
    search_fields = ['nombre', 'simbolo']

# --- REGISTRO DEL RESTO DE MODELOS ---
admin.site.register(InterfaceConsumo)
admin.site.register(PuntoMedicion)
admin.site.register(Equipo)
admin.site.register(CaracteristicaMedicion)
admin.site.register(CategoriaPuntoMedicion)
admin.site.register(DocumentoMedicion)
admin.site.register(RangoMedicion)

class MiembroDepartamentoInline(admin.TabularInline):
    model = PerfilUsuario
    fields = ('usuario', 'telefono', 'responsable')
    readonly_fields = ('usuario',)
    extra = 0
    can_delete = False
    verbose_name = "Miembro del Departamento"
    verbose_name_plural = "Miembros del Departamento"

    def has_add_permission(self, request, obj=None):
        return False

class PuestoTrabajoInline(admin.TabularInline):
    model = PuestoTrabajo
    extra = 0
    can_delete = True
    fields = ('nombre', 'descripcion')
    verbose_name = "Puesto de Trabajo"
    verbose_name_plural = "Puestos de Trabajo del Departamento"

@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'correo', 'responsable', 'aprobador', 'descripcion')
    search_fields = ('nombre', 'codigo', 'correo', 'responsable__username', 'responsable__first_name', 'responsable__last_name', 'aprobador__username', 'aprobador__first_name', 'aprobador__last_name')
    autocomplete_fields = ('responsable', 'aprobador')
    inlines = [MiembroDepartamentoInline, PuestoTrabajoInline]
    change_form_template = "admin/core/departamento/change_form.html"
class ServicioResource(resources.ModelResource):
    class Meta:
        model = Servicio
        fields = ('id', 'nombre', 'descripcion')
        export_order = ('id', 'nombre', 'descripcion')
        skip_unchanged = True
        report_skipped = True

@admin.register(Servicio)
class ServicioAdmin(ImportExportModelAdmin):
    resource_class = ServicioResource
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

class KPIResource(resources.ModelResource):
    servicio_nombre = fields.Field(
        column_name='servicio_nombre',
        attribute='servicio',
        widget=ForeignKeyWidget(Servicio, field='nombre')
    )

    class Meta:
        model = KPI
        fields = ('id', 'kpi', 'descripcion', 'servicio_nombre')
        export_order = ('id', 'kpi', 'servicio_nombre', 'descripcion')
        skip_unchanged = True
        report_skipped = True

@admin.register(KPI)
class KPIAdmin(ImportExportModelAdmin):
    resource_class = KPIResource
    list_display = ('kpi', 'servicio', 'descripcion')
    list_filter = ('servicio',)
    search_fields = ('kpi', 'descripcion', 'servicio__nombre')

@admin.register(VistaConsumoDiferencia)
class VistaConsumoDiferenciaAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'medidor_id', 'consumo', 'consumo_anterior', 'diferencia_consumo']
    list_filter = ['fecha', 'medidor_id']
    search_fields = ['medidor_id']
    readonly_fields = [f.name for f in VistaConsumoDiferencia._meta.fields]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(ElementoApp)
class ElementoAppAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'clave', 'activo', 'orden', 'get_grupos')
    list_filter = ('activo', 'grupos')
    search_fields = ('nombre', 'clave')
    filter_horizontal = ('grupos',)
    list_editable = ('activo', 'orden')
    ordering = ('orden', 'nombre')

    def get_grupos(self, obj):
        grupos = obj.grupos.all()
        if not grupos:
            return format_html('<span style="color:#10b981; font-weight:600;">✅ Todos</span>')
        return ', '.join(g.name for g in grupos)
    get_grupos.short_description = 'Visible para'


class AdminNavItemInline(admin.TabularInline):
    model = AdminNavItem
    extra = 1
    fk_name = "menu"
    fields = ("name", "url", "icon", "group", "permission", "order")
    ordering = ("group", "order")
    verbose_name = "Elemento"
    verbose_name_plural = "Elementos del menú"


class ColumnAdminNavItemInline(admin.TabularInline):
    model = AdminNavItem
    extra = 1
    fk_name = "column"
    fields = ("name", "url", "icon", "permission", "order")
    ordering = ("order",)
    verbose_name = "Elemento"
    verbose_name_plural = "Elementos de la columna"


class AdminNavColumnInline(admin.TabularInline):
    model = AdminNavColumn
    extra = 0
    fields = ("heading", "order")
    ordering = ("order",)
    verbose_name = "Columna"
    verbose_name_plural = "Columnas"
    classes = ("collapse",)
    help_text = "Define grupos para organizar los elementos del menú en columnas. Luego asigna estos grupos desde el campo 'Encabezado de columna' en cada elemento."


@admin.register(AdminNavMenu)
class AdminNavMenuAdmin(admin.ModelAdmin):
    list_display = ("name", "get_grupos", "order", "superuser_only", "active")
    list_editable = ("order", "superuser_only", "active")
    list_filter = ("active", "superuser_only", "grupos")
    search_fields = ("name",)
    ordering = ("order",)
    filter_horizontal = ("grupos",)
    fields = ("name", "icon", "color", "descripcion", "url", "grupos", "superuser_only", "order", "active")
    inlines = [AdminNavItemInline, AdminNavColumnInline]

    def get_grupos(self, obj):
        grupos = obj.grupos.all()
        if not grupos:
            return format_html('<span style="color:#10b981; font-weight:600;">✅ Todos</span>')
        return ', '.join(g.name for g in grupos)
    get_grupos.short_description = 'Visible para (rol)'


@admin.register(AdminNavColumn)
class AdminNavColumnAdmin(admin.ModelAdmin):
    list_display = ("__str__", "menu", "order")
    list_filter = ("menu",)
    ordering = ("menu", "order")
    inlines = [ColumnAdminNavItemInline]