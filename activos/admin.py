from django.db import models
from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from mptt.admin import DraggableMPTTAdmin
from .models import Activo, Categoria, Ubicacion, Marca, Modelo, Plano, VisorPlano, PinPlano

# ... (resto de registros)

from django.utils.html import format_html

@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ubicacion', 'visualizar_archivo', 'creado_en')
    list_filter = ('ubicacion',)
    search_fields = ('nombre', 'ubicacion__nombre')
    filter_horizontal = ('activos',)
    readonly_fields = ('visualizar_archivo',)

    def visualizar_archivo(self, obj):
        if obj.archivo:
            return format_html('<a href="{0}" target="_blank">📄 Ver Plano</a>', obj.archivo.url)
        return "No hay archivo"
    visualizar_archivo.short_description = "Visualizar"

class PinPlanoInline(admin.TabularInline):
    model = PinPlano
    extra = 1
    autocomplete_fields = ['activo']

@admin.register(VisorPlano)
class VisorPlanoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'plano', 'abrir_visor', 'creado_en')
    list_filter = ('plano',)
    search_fields = ('nombre', 'plano__nombre')
    inlines = [PinPlanoInline]

    def abrir_visor(self, obj):
        return format_html('<a href="/activos/visor/{0}/" target="_blank" class="button" style="background-color: #447e9b; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">👁️ Abrir Visor Interactivo</a>', obj.pk)
    abrir_visor.short_description = "Visor"

@admin.register(PinPlano)
class PinPlanoAdmin(admin.ModelAdmin):
    list_display = ('visor', 'activo', 'x', 'y', 'color')
    list_filter = ('visor', 'visor__plano')
    search_fields = ('visor__nombre', 'activo__nombre')
    autocomplete_fields = ['activo', 'visor']

@admin.register(Categoria)
class CategoriaAdmin(ImportExportModelAdmin):
    list_display = ('nombre', 'icono', 'descripcion')
    search_fields = ('nombre',)

class UbicacionResource(resources.ModelResource):
    """
    Resource personalizado para exportar/importar ubicaciones jerárquicas.
    
    IMPORTACIÓN: Solo necesitas proporcionar 'nombre' y 'padre_nombre'
    EXPORTACIÓN: Se generan automáticamente 'clave_unica' y 'ruta_completa'
    
    Permite múltiples ubicaciones con el mismo nombre en diferentes padres.
    Ej: Puedes tener "Nivel 1" en Torre A, Torre B, Torre C sin conflictos.
    """
    padre_nombre = fields.Field(
        column_name='padre_nombre',
        attribute='padre',
        widget=ForeignKeyWidget(Ubicacion, field='nombre')
    )
    
    # Campo ID como solo lectura para evitar errores si el ID del archivo ya no existe
    id = fields.Field(column_name='id', attribute='id', readonly=True)
    
    # Campos calculados automáticamente - SOLO para exportación
    clave_unica = fields.Field(
        column_name='clave_unica',
        attribute='get_clave_unica',
        readonly=True  # No se puede importar, solo exportar
    )
    
    ruta_completa = fields.Field(
        column_name='ruta_completa',
        attribute='ruta_completa',
        readonly=True  # No se puede importar, solo exportar
    )
    
    class Meta:
        model = Ubicacion
        # IMPORTANTE: Definimos campos de identidad para que NO use el ID del archivo
        # Esto permite que si el ID no existe (fue limpiado), lo cree o actualice por Nombre+Padre
        import_id_fields = ('nombre', 'padre_nombre')
        fields = ('id', 'nombre', 'padre_nombre', 'descripcion', 'ruta_completa', 'clave_unica')
        export_order = ('id', 'clave_unica', 'ruta_completa', 'nombre', 'padre_nombre', 'descripcion')
        skip_unchanged = True
        report_skipped = True
    
    def get_instance(self, instance_loader, row):
        """
        Busca la ubicación existente por la combinación única de nombre + padre.
        Ignoramos el ID del archivo para evitar errores si el registro fue recreado con otro ID.
        """
        nombre = str(row.get('nombre') or '').strip()
        padre_nombre = str(row.get('padre_nombre') or '').strip()
        
        if not nombre:
            return None
            
        # Buscar por lógica de negocio: Nombre + Padre
        try:
            padre = None
            if padre_nombre:
                # Buscar el padre. Si hay ambigüedad, tomamos el que aparezca primero.
                padre = Ubicacion.objects.filter(nombre=padre_nombre).first()
                if not padre:
                    # Si el padre no existe, no podemos encontrar la instancia hijo aún
                    return None
            
            # Buscar ubicación por nombre y su padre específico
            return Ubicacion.objects.filter(nombre=nombre, padre=padre).first()
        except Exception:
            return None


class ModeloInline(admin.TabularInline):
    model = Modelo
    extra = 1

@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)
    inlines = [ModeloInline]

@admin.register(Modelo)
class ModeloAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'marca', 'total_activos')
    list_filter = ('marca',)
    search_fields = ('nombre', 'marca__nombre')
    readonly_fields = ('lista_activos_ubicacion',)

    def total_activos(self, obj):
        return obj.activos.count()
    total_activos.short_description = 'Total Activos'

    def lista_activos_ubicacion(self, obj):
        activos = obj.activos.select_related('ubicacion').order_by('ubicacion__tree_id', 'ubicacion__lft')
        if not activos:
            return format_html('<span style="color: #999;">No hay activos registrados con este modelo.</span>')

        html = '<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">'
        html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        html += '<thead style="background: #f1f5f9; border-bottom: 1px solid #e2e8f0;">'
        html += '<tr>'
        html += '<th style="text-align: left; padding: 10px 15px; color: #64748b;">Ubicación</th>'
        html += '<th style="text-align: left; padding: 10px 15px; color: #64748b;">Código Interno</th>'
        html += '<th style="text-align: left; padding: 10px 15px; color: #64748b;">Nombre / Serie</th>'
        html += '<th style="text-align: center; padding: 10px 15px; color: #64748b;">Estado</th>'
        html += '<th style="text-align: center; padding: 10px 15px; color: #64748b;">Acción</th>'
        html += '</tr></thead><tbody>'

        for activo in activos:
            ubicacion_str = activo.ubicacion.ruta_completa if activo.ubicacion else '<span style="color: #dc3545;">Sin Ubicación</span>'
            estado_color = {
                'OPERATIVO': '#10b981',
                'MANTENIMIENTO': '#f59e0b',
                'REPARACION': '#ef4444',
                'OBSOLETO': '#64748b'
            }.get(activo.estado, '#000')

            html += f'<tr style="border-bottom: 1px solid #f1f5f9;">'
            html += f'<td style="padding: 10px 15px; font-weight: 500;">{ubicacion_str}</td>'
            html += f'<td style="padding: 10px 15px; color: #007bff; font-family: monospace;">{activo.codigo_interno or "---"}</td>'
            html += f'<td style="padding: 10px 15px;">{activo.nombre}<br><small style="color: #94a3b8;">S/N: {activo.serie or "N/A"}</small></td>'
            html += f'<td style="padding: 10px 15px; text-align: center;">'
            html += f'<span style="background: {estado_color}15; color: {estado_color}; padding: 3px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 700;">{activo.get_estado_display()}</span>'
            html += f'</td>'
            html += f'<td style="padding: 10px 15px; text-align: center;">'
            html += f'<a href="/admin/activos/activo/{activo.id}/change/" target="_blank" style="color: #64748b;"><ion-icon name="create-outline" style="font-size: 1.1rem;"></ion-icon></a>'
            html += f'</td></tr>'

        html += '</tbody></table></div>'
        return format_html(html)
    lista_activos_ubicacion.short_description = 'Activos Clasificados por Ubicación'

    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'marca')
        }),
        ('Distribución de Activos', {
            'fields': ('lista_activos_ubicacion',),
            'description': 'Listado completo de equipos físicos asociados a este modelo, organizados jerárquicamente por su ubicación.'
        }),
    )

from import_export.admin import ImportExportModelAdmin, ImportExportMixin

@admin.register(Ubicacion)
class UbicacionAdmin(ImportExportMixin, DraggableMPTTAdmin):
    """
    Admin que combina la funcionalidad de drag-and-drop de MPTT 
    con la capacidad de import/export de django-import-export.
    """
    resource_class = UbicacionResource
    mptt_indent_field = "nombre"
    list_display = ('tree_actions', 'indented_title', 'orden', 'descripcion')
    list_display_links = ('indented_title',)
    list_editable = ('orden',)
    search_fields = ('nombre',)
    list_filter = ('padre',)

@admin.register(Activo)
class ActivoAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ('codigo_interno', 'nombre', 'get_marca', 'modelo', 'serie', 'categoria', 'estado', 'ubicacion', 'responsable')
    list_filter = ('estado', 'categoria', 'modelo__marca', 'creado_en', 'ubicacion')
    search_fields = ('nombre', 'codigo_interno', 'serie', 'modelo__marca__nombre', 'modelo__nombre', 'marca_legacy', 'modelo_legacy', 'ubicacion__nombre', 'ubicacion_legacy')
    readonly_fields = ('creado_en', 'actualizado_en', 'ver_en_plano')

    def changelist_view(self, request, extra_context=None):
        if request.GET.get('_popup'):
            from .models import Ubicacion, Activo
            
            # Obtener todas las ubicaciones en orden jerárquico (MPTT)
            ubicaciones = Ubicacion.objects.all().order_by('tree_id', 'lft')
            
            # Obtener activos base (ignorando filtros del admin que puedan restringir el popup involuntariamente)
            queryset = Activo.objects.all().select_related('ubicacion', 'categoria')
            
            # El popup de Django envía el término de búsqueda en 'q'
            search_term = request.GET.get('q')
            if search_term:
                queryset = queryset.filter(
                    models.Q(nombre__icontains=search_term) | 
                    models.Q(codigo_interno__icontains=search_term) |
                    models.Q(serie__icontains=search_term)
                )

            # Organizar datos para el árbol: {"ubicacion_id": {"categoria_id": {"nombre": '...', activos: []}}}
            tree_data = {}
            for activo in queryset:
                if not activo.ubicacion: continue
                u_id = str(activo.ubicacion.id)
                c_id = str(activo.categoria.id) if activo.categoria else "0"
                c_nombre = activo.categoria.nombre if activo.categoria else "Sin Categoría"
                
                if u_id not in tree_data:
                    tree_data[u_id] = {}
                if c_id not in tree_data[u_id]:
                    tree_data[u_id][c_id] = {'nombre': c_nombre, 'activos': []}
                
                tree_data[u_id][c_id]['activos'].append({
                    'id': activo.id,
                    'nombre': activo.nombre,
                    'codigo_interno': activo.codigo_interno or 'S/C',
                    'estado': activo.get_estado_display()
                })

            extra_context = extra_context or {}
            extra_context.update({
                'tree_data': tree_data,
                'ubicaciones': ubicaciones,
                'is_popup': True,
                'title': 'Seleccionar Activo (Explorador Jerárquico)'
            })
            # Cambiar la plantilla solo para el popup
            self.change_list_template = 'admin/activos/activo/lookup_tree.html'
            
        else:
            # Restaurar la plantilla original si no es popup
            self.change_list_template = None
            
        return super().changelist_view(request, extra_context=extra_context)
    
    def get_marca(self, obj):
        if obj.modelo:
            return obj.modelo.marca
        return obj.marca_legacy
    get_marca.short_description = 'Marca'

    def ver_en_plano(self, obj):
        pines = obj.pines_planos.all()
        if not pines:
            return format_html('<span style="color: #999;">❌ No ubicado en planos</span>')
        
        html = '<div style="display: flex; flex-wrap: wrap; gap: 10px;">'
        for pin in pines:
            html += format_html(
                '<a href="/activos/visor/{0}/" target="_blank" style="background: #1e293b; color: white; padding: 8px 12px; border-radius: 8px; border: 1px solid #00d2ff; text-decoration: none; display: flex; align-items: center; gap: 8px;">'
                '<span style="color: #00d2ff; font-size: 1.2rem;">📍</span>'
                '<div>'
                '<div style="font-weight: bold; font-size: 0.8rem;">{1}</div>'
                '<div style="font-size: 0.7rem; opacity: 0.7;">Ver en Plano</div>'
                '</div>'
                '</a>',
                pin.visor.id,
                pin.visor.nombre
            )
        html += '</div>'
        return format_html(html)
    ver_en_plano.short_description = 'Ubicación en Planos'

    fieldsets = (
        ('Identificación', {
            'fields': ('nombre', 'codigo_interno', 'serie', 'categoria')
        }),
        ('Detalles Técnicos', {
            'fields': ('modelo', 'marca_legacy', 'modelo_legacy', 'descripcion', 'foto')
        }),
        ('Estado y Ubicación', {
            'fields': ('estado', 'ubicacion', 'ubicacion_legacy', 'responsable', 'ver_en_plano')
        }),
        ('Información Financiera', {
            'fields': ('fecha_compra', 'costo')
        }),
        ('Sistema', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )
