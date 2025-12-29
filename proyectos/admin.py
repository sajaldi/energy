from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Proyecto, Actividad, DocumentoProyecto


class DocumentoProyectoInline(admin.TabularInline):
    """Inline para agregar documentos al proyecto como subgrid"""
    model = DocumentoProyecto
    extra = 1
    fields = ('documento', 'nota', 'ver_documento')
    readonly_fields = ('ver_documento',)
    autocomplete_fields = ('documento',)
    verbose_name = "Documento"
    verbose_name_plural = "Documentos del Proyecto"
    
    def ver_documento(self, obj):
        if obj.documento_id:
            return format_html(
                '<a href="/admin/documentos/documento/{}/change/" target="_blank" '
                'style="color: #2563eb;">📄 Ver</a>',
                obj.documento_id
            )
        return "-"
    ver_documento.short_description = "Acción"


class ActividadInline(admin.TabularInline):
    model = Actividad
    extra = 1
    fields = ('nombre', 'estado', 'prioridad', 'asignado_a', 'fecha_inicio', 'fecha_fin', 'color', 'orden')
    autocomplete_fields = ('asignado_a',)
    ordering = ('orden', 'creado_en')


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'estado_badge', 'responsable', 'avance_bar', 'total_docs', 'abrir_visores', 'creado_en')
    list_filter = ('estado', 'responsable', 'ubicacion')
    search_fields = ('codigo', 'nombre', 'descripcion')
    search_fields = ('nombre', 'codigo', 'visores__nombre')
    autocomplete_fields = ('responsable', 'ubicacion')
    readonly_fields = ('creado_en', 'actualizado_en', 'resumen_actividades')
    inlines = [ActividadInline, DocumentoProyectoInline]
    
    # Para M2M usamos filter_horizontal
    filter_horizontal = ('visores',)
    
    fieldsets = (
        ('Información General', {
            'fields': ('codigo', 'nombre', 'descripcion', 'responsable', 'ubicacion', 'nota')
        }),
        ('Visualización', {
            'fields': ('visores',),
            'description': 'Seleccione los visores donde se ubicarán las actividades de este proyecto.'
        }),
        ('Sistema', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )
    def abrir_visores(self, obj):
        links = []
        if obj.pk:
            for v in obj.visores.all():
                url = reverse('activos:visor_plano', args=[v.id])
                links.append(f'<a href="{url}" target="_blank" class="button" style="background: #10b981; color: white; padding: 2px 8px; border-radius: 4px; text-decoration: none; margin-right: 4px; font-size: 0.75rem;">{v.nombre}</a>')
        return format_html("".join(links)) if links else "-"
    
    abrir_visores.short_description = "Ver en Planos"
    
    def total_docs(self, obj):
        count = obj.documentos_proyecto.count()
        if count == 0:
            return format_html('<span style="color: #94a3b8;">0</span>')
        return format_html('<span style="color: #2563eb; font-weight: 600;">{}</span>', count)
    total_docs.short_description = 'Docs'
    
    def estado_badge(self, obj):
        colores = {
            'PLANIFICACION': '#3b82f6',
            'EJECUCION': '#10b981',
            'PAUSADO': '#f59e0b',
            'COMPLETADO': '#6366f1',
            'CANCELADO': '#ef4444',
        }
        color = colores.get(obj.estado, '#64748b')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; border-radius: 12px; '
            'font-size: 0.75rem; font-weight: 600;">{}</span>',
            color, obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def avance_bar(self, obj):
        pct = obj.porcentaje_avance
        color = '#10b981' if pct == 100 else '#3b82f6'
        return format_html(
            '<div style="width: 100px; background: #e2e8f0; border-radius: 8px; overflow: hidden;">'
            '<div style="width: {}%; height: 8px; background: {};"></div>'
            '</div>'
            '<span style="font-size: 0.7rem; color: #64748b; margin-left: 5px;">{}/{}</span>',
            pct, color, obj.actividades_completadas, obj.total_actividades
        )
    avance_bar.short_description = 'Avance'
    
    def resumen_actividades(self, obj):
        actividades = obj.actividades.all()[:10]
        if not actividades:
            return format_html('<span style="color: #94a3b8;">Sin actividades registradas</span>')
        
        html = '<div style="display: flex; flex-direction: column; gap: 8px;">'
        for act in actividades:
            estado_color = {
                'PENDIENTE': '#94a3b8',
                'EN_PROGRESO': '#3b82f6',
                'COMPLETADA': '#10b981',
                'BLOQUEADA': '#ef4444',
            }.get(act.estado, '#64748b')
            
            html += f'''
            <div style="display: flex; align-items: center; gap: 10px; padding: 8px; 
                        background: #f8fafc; border-radius: 6px; border-left: 3px solid {act.color};">
                <span style="width: 8px; height: 8px; border-radius: 50%; background: {estado_color};"></span>
                <span style="flex: 1; font-weight: 500;">{act.nombre}</span>
                <span style="font-size: 0.75rem; color: #64748b;">{act.get_estado_display()}</span>
            </div>
            '''
        html += '</div>'
        return format_html(html)
    resumen_actividades.short_description = 'Actividades Recientes'


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'proyecto_link', 'estado_badge', 'prioridad_badge', 'asignado_a', 'fecha_fin')
    list_filter = ('estado', 'prioridad', 'proyecto', 'asignado_a')
    search_fields = ('nombre', 'descripcion', 'proyecto__codigo', 'proyecto__nombre')
    autocomplete_fields = ('proyecto', 'asignado_a')
    list_select_related = ('proyecto', 'asignado_a')
    
    fieldsets = (
        ('Información', {
            'fields': ('proyecto', 'nombre', 'descripcion')
        }),
        ('Estado y Prioridad', {
            'fields': ('estado', 'prioridad', 'color')
        }),
        ('Planificación', {
            'fields': ('fecha_inicio', 'fecha_fin', 'asignado_a', 'orden')
        }),
    )
    
    def proyecto_link(self, obj):
        return format_html(
            '<a href="/admin/proyectos/proyecto/{}/change/" style="color: #2563eb;">{}</a>',
            obj.proyecto.id, obj.proyecto.codigo
        )
    proyecto_link.short_description = 'Proyecto'
    
    def estado_badge(self, obj):
        colores = {
            'PENDIENTE': '#94a3b8',
            'EN_PROGRESO': '#3b82f6',
            'COMPLETADA': '#10b981',
            'BLOQUEADA': '#ef4444',
        }
        color = colores.get(obj.estado, '#64748b')
        return format_html(
            '<span style="background: {}20; color: {}; padding: 3px 8px; border-radius: 12px; '
            'font-size: 0.75rem; font-weight: 600;">{}</span>',
            color, color, obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def prioridad_badge(self, obj):
        colores = {
            'BAJA': '#10b981',
            'MEDIA': '#3b82f6',
            'ALTA': '#f59e0b',
            'CRITICA': '#ef4444',
        }
        color = colores.get(obj.prioridad, '#64748b')
        return format_html(
            '<span style="color: {}; font-weight: 600;">{}</span>',
            color, obj.get_prioridad_display()
        )
    prioridad_badge.short_description = 'Prioridad'
