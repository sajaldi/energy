from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import BienAfecto, HistorialBienAfecto

class HistorialBienAfectoInline(admin.TabularInline):
    model = HistorialBienAfecto
    extra = 0
    fields = ('activo', 'fecha_alta', 'usuario_alta', 'fecha_baja', 'usuario_baja', 'motivo_baja', 'get_estado_badge')
    readonly_fields = ('fecha_alta', 'usuario_alta', 'fecha_baja', 'usuario_baja', 'get_estado_badge')
    autocomplete_fields = ('activo',)
    can_delete = False
    
    def get_estado_badge(self, obj):
        if not obj.id:
            return "-"
        
        if obj.esta_activo:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">✓ ACTIVO</span>'
            )
        else:
            return format_html(
                '<span style="background: #ef4444; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">✗ BAJA</span>'
            )
    get_estado_badge.short_description = "Estado"

from documentos.admin_mayan import MayanDocumentInline

@admin.register(BienAfecto)
class BienAfectoAdmin(admin.ModelAdmin):
    list_display = ('codigo_interno', 'nombre', 'get_activo_actual', 'ubicacion', 'responsable', 'get_total_reemplazos', 'actualizado_en')
    list_filter = ('familia', 'ubicacion', 'responsable')
    search_fields = ('codigo_interno', 'nombre')
    autocomplete_fields = ('ubicacion', 'familia', 'responsable')
    inlines = [HistorialBienAfectoInline, MayanDocumentInline]
    readonly_fields = ('creado_en', 'actualizado_en', 'get_activo_actual_detalle', 'get_estadisticas')
    
    
    fieldsets = (
        ('Información del Bien Afecto', {
            'fields': ('codigo_interno', 'nombre', 'familia')
        }),
        ('Ubicación y Responsable', {
            'fields': ('ubicacion', 'responsable')
        }),
        ('Activo Actual', {
            'fields': ('get_activo_actual_detalle',),
            'description': 'Equipo físico actualmente asignado a este bien afecto'
        }),
        ('Estadísticas', {
            'fields': ('get_estadisticas',),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )
    
    def get_total_reemplazos(self, obj):
        """Muestra el total de reemplazos en la lista"""
        total = obj.historial.count() - 1  # -1 porque el primero no es reemplazo
        if total > 0:
            return format_html(
                '<span style="background: #fbbf24; color: #78350f; padding: 2px 8px; border-radius: 8px; font-weight: 600; font-size: 0.75rem;">{} reemplazos</span>',
                total
            )
        return format_html('<span style="color: #94a3b8;">Sin reemplazos</span>')
    get_total_reemplazos.short_description = "Reemplazos"
    
    def get_estadisticas(self, obj):
        """Muestra estadísticas del bien afecto"""
        total_activos = obj.historial.count()
        vida_util = obj.tiempo_promedio_vida_util()
        
        if vida_util:
            dias = vida_util.days
            if dias >= 365:
                vida_util_str = f"{dias // 365} años, {(dias % 365) // 30} meses"
            elif dias >= 30:
                vida_util_str = f"{dias // 30} meses, {dias % 30} días"
            else:
                vida_util_str = f"{dias} días"
        else:
            vida_util_str = "N/A (sin datos suficientes)"
        
        return format_html(
            '<div style="padding: 15px; background: #f1f5f9; border-radius: 8px;">'
            '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;">'
            '<div>'
            '<div style="font-size: 0.75rem; color: #64748b; text-transform: uppercase; font-weight: 600;">Total de Activos</div>'
            '<div style="font-size: 1.5rem; font-weight: 700; color: #1e293b;">{}</div>'
            '</div>'
            '<div>'
            '<div style="font-size: 0.75rem; color: #64748b; text-transform: uppercase; font-weight: 600;">Vida Útil Promedio</div>'
            '<div style="font-size: 1.5rem; font-weight: 700; color: #1e293b;">{}</div>'
            '</div>'
            '</div>'
            '</div>',
            total_activos,
            vida_util_str
        )
    get_estadisticas.short_description = "Estadísticas de Uso"
    
    def get_activo_actual(self, obj):
        """Muestra el activo actual en la lista"""
        activo = obj.activo_actual
        if activo:
            url = f"/admin/activos/activo/{activo.id}/change/"
            return format_html(
                '<a href="{}" style="font-weight: 600; color: #2563eb;">{}</a>',
                url, activo.nombre
            )
        return format_html('<span style="color: #94a3b8; font-style: italic;">Sin asignar</span>')
    get_activo_actual.short_description = "Activo Actual"
    
    def get_activo_actual_detalle(self, obj):
        """Muestra detalles del activo actual en el formulario"""
        activo = obj.activo_actual
        if not activo:
            return format_html(
                '<div style="padding: 15px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; color: #991b1b;">'
                '<strong>⚠️ Sin activo asignado</strong><br>'
                '<small>Use la sección "Historial de Bien Afecto" abajo para dar de alta un activo.</small>'
                '</div>'
            )
        
        historial = obj.historial.filter(fecha_baja__isnull=True).first()
        fecha_alta = historial.fecha_alta.strftime('%d/%m/%Y %H:%M') if historial else 'N/A'
        usuario_alta = historial.usuario_alta.username if historial and historial.usuario_alta else 'Sistema'
        
        url = f"/admin/activos/activo/{activo.id}/change/"
        
        return format_html(
            '<div style="padding: 15px; background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px;">'
            '<div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">'
            '<span style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">✓ ACTIVO</span>'
            '<a href="{}" target="_blank" style="font-size: 1.1rem; font-weight: 700; color: #047857; text-decoration: none;">{}</a>'
            '</div>'
            '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; font-size: 0.85rem; color: #065f46;">'
            '<div><strong>Código:</strong> {}</div>'
            '<div><strong>Serie:</strong> {}</div>'
            '<div><strong>Modelo:</strong> {}</div>'
            '<div><strong>Estado:</strong> {}</div>'
            '<div><strong>Fecha Alta:</strong> {}</div>'
            '<div><strong>Dado de Alta por:</strong> {}</div>'
            '</div>'
            '</div>',
            url,
            activo.nombre,
            activo.codigo_interno or 'S/C',
            activo.serie or 'N/A',
            activo.modelo if activo.modelo else 'N/A',
            activo.get_estado_display(),
            fecha_alta,
            usuario_alta
        )
    get_activo_actual_detalle.short_description = "Equipo Asignado"

@admin.register(HistorialBienAfecto)
class HistorialBienAfectoAdmin(admin.ModelAdmin):
    list_display = ('bien_afecto', 'activo', 'fecha_alta', 'usuario_alta', 'get_estado', 'fecha_baja', 'motivo_baja')
    list_filter = ('motivo_baja', 'fecha_alta', 'fecha_baja')
    search_fields = ('bien_afecto__codigo_interno', 'bien_afecto__nombre', 'activo__nombre', 'activo__codigo_interno')
    autocomplete_fields = ('bien_afecto', 'activo')
    readonly_fields = ('fecha_alta', 'usuario_alta', 'fecha_baja', 'usuario_baja')
    
    fieldsets = (
        ('Relación', {
            'fields': ('bien_afecto', 'activo')
        }),
        ('Alta', {
            'fields': ('fecha_alta', 'usuario_alta')
        }),
        ('Baja', {
            'fields': ('fecha_baja', 'usuario_baja', 'motivo_baja', 'observaciones_baja'),
            'description': 'Complete estos campos solo cuando el activo sea dado de baja'
        }),
    )
    
    def get_estado(self, obj):
        if obj.esta_activo:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">✓ ACTIVO</span>'
            )
        return format_html(
            '<span style="background: #ef4444; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">✗ BAJA</span>'
        )
    get_estado.short_description = "Estado"
    
    def save_model(self, request, obj, form, change):
        """Auto-asignar usuario en alta o baja"""
        if not change:  # Nuevo registro (alta)
            obj.usuario_alta = request.user
        elif 'fecha_baja' in form.changed_data and obj.fecha_baja:  # Se está dando de baja
            obj.usuario_baja = request.user
            if not obj.fecha_baja:
                obj.fecha_baja = timezone.now()
        
        super().save_model(request, obj, form, change)
