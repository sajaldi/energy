from django.contrib import admin
from django.db import models
from django.contrib.admin import widgets
from django.utils.html import format_html
from django.db.models import Count
from .models import Familia, Activo, PinPlano, Modelo, PuntoMedicion, DocumentoMedicion, Ubicacion, Plano
from inventarios.models import CompatibilidadMaterial
from auditorias.models import ResultadoAuditoria

class SubFamiliaInline(admin.TabularInline):
    model = Familia
    fk_name = 'padre'
    extra = 1
    verbose_name = "Sub-Familia"
    verbose_name_plural = "Sub-Familias"
    formfield_overrides = {
        models.TextField: {'widget': widgets.AdminTextInputWidget(attrs={'style': 'width: 100%;'})},
    }

class ActivoFamiliaInline(admin.TabularInline):
    model = Activo
    extra = 0
    fields = ('nombre', 'codigo_interno', 'modelo', 'estado', 'ubicacion')
    autocomplete_fields = ('modelo', 'ubicacion')
    readonly_fields = ('nombre', 'codigo_interno', 'modelo', 'estado', 'ubicacion')
    can_delete = False
    show_change_link = True
    verbose_name = "Activo en esta Familia"
    verbose_name_plural = "Activos vinculados a esta Familia"

    def has_add_permission(self, request, obj=None):
        return False

class PinPlanoInline(admin.TabularInline):
    model = PinPlano
    extra = 1
    autocomplete_fields = ['activo']

class CompatibilidadMaterialInline(admin.TabularInline):
    model = CompatibilidadMaterial
    extra = 1
    autocomplete_fields = ['material']

class ModeloInline(admin.TabularInline):
    model = Modelo
    extra = 1
    fields = ('nombre', 'categoria', 'precio_promedio')
    autocomplete_fields = ('categoria',)

class ComponenteActivoInline(admin.TabularInline):
    model = Activo
    fk_name = 'padre'
    extra = 1
    verbose_name = "Componente / Sub-equipo"
    verbose_name_plural = "Componentes / Sub-equipos (Hijos)"
    fields = ('nombre', 'codigo_interno', 'modelo', 'estado', 'ubicacion')
    autocomplete_fields = ('modelo', 'ubicacion')
    show_change_link = True

class PuntoMedicionInline(admin.TabularInline):
    model = PuntoMedicion
    extra = 1
    fields = ('nombre', 'codigo', 'unidad', 'es_acumulativo', 'valor_objetivo', 'get_valor_actual')
    readonly_fields = ('get_valor_actual',)

    @admin.display(description="Valor Actual")
    def get_valor_actual(self, obj):
        val = obj.valor_actual
        if val is not None:
            return f"{val} {obj.unidad}"
        return "---"

class DocumentoMedicionInline(admin.TabularInline):
    model = DocumentoMedicion
    extra = 1
    fields = ('punto', 'valor', 'fecha_lectura', 'tecnico', 'observaciones')
    autocomplete_fields = ('punto', 'tecnico')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "punto":
            # Si estamos en la vista de cambio de un activo (pk presente en URL)
            import re
            match = re.search(r'activo/(\d+)/change', request.path)
            if match:
                activo_id = match.group(1)
                kwargs["queryset"] = PuntoMedicion.objects.filter(activo_id=activo_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class AuditoriasActivoInline(admin.TabularInline):
    model = ResultadoAuditoria
    extra = 0
    fields = ('auditoria', 'estado', 'get_ubicacion_esperada', 'get_ubicacion_encontrada', 'fecha_escaneo', 'get_sync_button')
    readonly_fields = ('auditoria', 'estado', 'get_ubicacion_esperada', 'get_ubicacion_encontrada', 'fecha_escaneo', 'get_sync_button')
    can_delete = False
    verbose_name = "Auditoría Realizada"
    verbose_name_plural = "Historial de Auditorías"

    def get_ubicacion_esperada(self, obj):
        if obj.ubicacion_esperada:
            return obj.ubicacion_esperada.ruta_completa
        return "---"
    get_ubicacion_esperada.short_description = "Ubicación Esperada"

    def get_ubicacion_encontrada(self, obj):
        if obj.ubicacion_encontrada:
            return obj.ubicacion_encontrada.ruta_completa
        return "---"
    get_ubicacion_encontrada.short_description = "Ubicación Encontrada"

    def get_sync_button(self, obj):
        if not obj.id or not obj.ubicacion_encontrada:
            return "---"
        return format_html(
            '<a href="/admin/activos/activo/{}/sync-audit/{}/" class="button" style="background-color: #f1f5f9; color: #333; border: 1px solid #ccc; padding: 4px 8px; border-radius: 4px;">🔄 Sincronizar Ubicación</a>',
            obj.activo.id,
            obj.id
        )
    get_sync_button.short_description = "Acción"

class UbicacionHijaInline(admin.TabularInline):
    model = Ubicacion
    fk_name = 'padre'
    extra = 1
    verbose_name = "Sub-Ubicación"
    verbose_name_plural = "Sub-Ubicaciones (Niveles Hijos)"
    fields = ('render_icon', 'nombre', 'orden', 'categoria', 'total_count', 'descripcion')
    autocomplete_fields = ['categoria']
    readonly_fields = ('render_icon', 'total_count')
    show_change_link = True

    def render_icon(self, obj):
        icon = "📍"
        if obj.tipo == 'EDIFICIO': icon = "🏢"
        elif obj.tipo == 'NIVEL': icon = "layers" # Ionicons name, but here we use emoji for simplicity in inline or maybe check if we can use ion-icon
        elif obj.tipo == 'ESPACIO': icon = "🚪"
        
        # Using ion-icon if supported or emoji
        if obj.tipo == 'NIVEL':
            return format_html('<div style="font-size: 1.2rem; display: flex; align-items: center; justify-content: center; height: 100%; color: #64748b;">🔢</div>')
        elif obj.tipo == 'EDIFICIO':
            return format_html('<div style="font-size: 1.2rem; display: flex; align-items: center; justify-content: center; height: 100%; color: #1e293b;">🏢</div>')
        
        return format_html('<div style="font-size: 1.2rem; display: flex; align-items: center; justify-content: center; height: 100%;">📍</div>')
    render_icon.short_description = 'Tipo'

    def total_count(self, obj):
        if not obj.pk:
            return format_html('<span style="color: #94a3b8; font-size: 0.7rem;">(Pendiente)</span>')
        count = getattr(obj, '_activos_count', 0)
        if count == 0:
            return format_html('<span style="color: #cbd5e1; font-size: 0.75rem;">Vacío</span>')
        return format_html(
            '<div style="background: #eff6ff; color: #2563eb; padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 0.7rem; display: inline-block; border: 1px solid #dbeafe;">'
            '{} EQUIPOS'
            '</div>', count
        )
    total_count.short_description = 'Equipos'

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _activos_count=Count('activos')
        ).select_related('categoria')

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'nombre':
            formfield.widget.attrs.update({'style': 'width: 250px;'})
        elif db_field.name == 'orden':
            formfield.widget.attrs.update({'style': 'width: 60px;'})
        elif db_field.name == 'descripcion':
            from django.forms import TextInput
            formfield.widget = TextInput(attrs={'style': 'width: 100%; min-width: 300px;', 'placeholder': 'Opcional...'})
        return formfield

class PlanoInline(admin.StackedInline):
    model = Plano
    extra = 0
    show_change_link = True
    fields = ('nombre', 'documento', 'archivo', 'descripcion', 'ver_visores')
    readonly_fields = ('ver_visores',)
    autocomplete_fields = ['documento']

    def ver_visores(self, obj):
        if obj.pk:
            # Aprovecha el prefetch_related('visores') del get_queryset
            visores = obj.visores.all()
            if visores:
                html = '<div style="display: flex; gap: 5px; flex-wrap: wrap;">'
                for v in visores:
                     html += f'<a href="/activos/visor/{v.pk}/" target="_blank" class="button" style="background-color: #447e9b; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none; font-size: 0.8rem;">👁️ {v.nombre}</a>'
                html += '</div>'
                return format_html(html)
            return format_html('<span style="color: #64748b; font-style: italic;">No hay visores configurados. Guarde el plano y agregue uno desde la administración de planos.</span>')
        return "-"
    ver_visores.short_description = "Visores Interactivos"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('visores', 'documento')

class UbicacionEnPlanosInline(admin.TabularInline):
    """
    Muestra los planos donde esta ubicación ha sido dibujada/marcada (como zona hijo).
    """
    model = PinPlano
    fk_name = 'ubicacion'
    extra = 0
    verbose_name = "Aparición en Plano"
    verbose_name_plural = "Planos donde aparece esta ubicación (Zonas/Pines)"
    fields = ('link_plano', 'visor', 'preview_zona', 'abrir_visor')
    readonly_fields = ('link_plano', 'visor', 'preview_zona', 'abrir_visor')
    can_delete = False
    max_num = 0

    def link_plano(self, obj):
        if obj.visor and obj.visor.plano:
            return format_html(
                '<a href="/admin/activos/plano/{0}/change/" target="_blank" style="font-weight:bold;">📄 {1}</a>'
                '<br><span style="color:#64748b; font-size:0.8em;">Ubicación Padre: {2}</span>',
                obj.visor.plano.id,
                obj.visor.plano.nombre,
                obj.visor.plano.ubicacion.nombre if obj.visor.plano.ubicacion else "N/A"
            )
        return "-"
    link_plano.short_description = "Plano Contenedor"

    def preview_zona(self, obj):
        if obj.ancho > 0:
            return format_html(f'<span style="color:var(--primary); font-weight:600;">⬚ Zona ({int(obj.ancho)}x{int(obj.alto)}px)</span>')
        return "📍 Punto (Pin)"
    preview_zona.short_description = "Tipo Marcador"

    def abrir_visor(self, obj):
        return format_html(
            '<a href="/activos/visor/{0}/" target="_blank" class="button" style="background:#447e9b; color:white; padding:4px 10px; border-radius:4px; text-decoration:none;">'
            '👁️ Ver en Plano'
            '</a>',
            obj.visor.id
        )
    abrir_visor.short_description = "Acción"
    
    def has_add_permission(self, request, obj=None):
        return False
