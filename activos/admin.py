from django.db import models
from django.contrib import admin
from django.db.models import Count
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from django.contrib.auth.models import User
from .models import Activo, Categoria, Ubicacion, Marca, Modelo, Plano, VisorPlano, PinPlano

# ... (resto de registros)

from django.utils.html import format_html

@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ubicacion', 'visualizar_archivo', 'creado_en')
    list_filter = ('ubicacion',)
    list_select_related = ('ubicacion',)
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
    list_select_related = ('plano',)
    search_fields = ('nombre', 'plano__nombre')
    inlines = [PinPlanoInline]

    def abrir_visor(self, obj):
        return format_html('<a href="/activos/visor/{0}/" target="_blank" class="button" style="background-color: #447e9b; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">👁️ Abrir Visor Interactivo</a>', obj.pk)
    abrir_visor.short_description = "Visor"

@admin.register(PinPlano)
class PinPlanoAdmin(admin.ModelAdmin):
    list_display = ('visor', 'activo', 'x', 'y', 'color')
    list_filter = ('visor', 'visor__plano')
    list_select_related = ('visor', 'activo')
    search_fields = ('visor__nombre', 'activo__nombre')
    autocomplete_fields = ['activo', 'visor']

@admin.register(Categoria)
class CategoriaAdmin(ImportExportModelAdmin):
    list_display = ('nombre', 'icono', 'descripcion')
    search_fields = ('nombre',)

class SmartParentWidget(ForeignKeyWidget):
    """
    Widget inteligente que maneja casos donde múltiples objetos coinciden
    con el nombre (común en jerarquías no únicas).
    Devuelve el primer objeto encontrado en lugar de lanzar MultipleObjectsReturned.
    """
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        try:
            return self.get_queryset(value, row, **kwargs).filter(nombre=value).first()
        except Exception:
            return None

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
        widget=SmartParentWidget(Ubicacion, field='nombre')
    )
    
    # Campo ID como solo lectura para evitar errores si el ID del archivo ya no existe
    id = fields.Field(column_name='id', attribute='id', readonly=True)
    
    # Campos calculados automáticamente - SOLO para exportación
    clave_unica = fields.Field(
        column_name='clave_unica',
        readonly=True
    )
    
    ruta_completa = fields.Field(
        column_name='ruta_completa',
        readonly=True
    )
    
    class Meta:
        model = Ubicacion
        import_id_fields = ('nombre', 'padre_nombre')
        fields = ('id', 'nombre', 'padre', 'orden', 'descripcion')
        export_order = ('id', 'clave_unica', 'ruta_completa', 'nombre', 'padre_nombre', 'orden', 'descripcion')
        skip_unchanged = True
        report_skipped = True
        use_bulk = True
        batch_size = 1000

    def before_export(self, queryset, *args, **kwargs):
        """Precarga todas las rutas en memoria para evitar N+1 queries"""
        self.ruta_cache = {}
        self.clave_cache = {}
        # Usamos orden jerárquico manual (padre_id, orden)
        all_locs = Ubicacion.objects.all().order_by('padre_id', 'orden', 'nombre')
        
        # Mapa para construcción de rutas
        loc_map = {l.id: l for l in all_locs}
        
        for loc in all_locs:
            path = [loc.nombre]
            curr = loc.padre
            while curr:
                # Usamos el mapa para evitar queries
                curr_obj = loc_map.get(curr.id)
                if curr_obj:
                    path.append(curr_obj.nombre)
                    curr = curr_obj.padre
                else:
                    break
            self.ruta_cache[loc.id] = " → ".join(reversed(path))
            self.clave_cache[loc.id] = "|".join(reversed(path))

    def dehydrate_ruta_completa(self, obj):
        return self.ruta_cache.get(obj.id, "")

    def dehydrate_clave_unica(self, obj):
        return self.clave_cache.get(obj.id, "")

    def before_import(self, dataset, *args, **kwargs):
        """Precarga todas las ubicaciones para evitar N+1 queries"""
        # Mapa de (nombre, padre_id) -> id para get_instance
        self.instance_map = {}
        # Mapa de nombre -> id (para resolver padres por nombre rápido)
        self.name_to_id = {}
        
        for loc in Ubicacion.objects.all().values('id', 'nombre', 'padre_id'):
            self.instance_map[(loc['nombre'], loc['padre_id'])] = loc['id']
            if loc['nombre'] not in self.name_to_id:
                self.name_to_id[loc['nombre']] = loc['id']

    def before_import_row(self, row, **kwargs):
        """Resuelve el padre usando el caché en lugar de queries"""
        padre_nombre = str(row.get('padre_nombre') or '').strip()
        if padre_nombre:
            row['padre_id_fast'] = self.name_to_id.get(padre_nombre)
        else:
            row['padre_id_fast'] = None

    def init_instance(self, row=None):
        """Inicializa instancia con el padre resuelto"""
        instance = super().init_instance(row)
        padre_id = row.get('padre_id_fast')
        if padre_id:
            instance.padre_id = padre_id
        return instance

    def get_instance(self, instance_loader, row):
        """Usa el mapa en memoria para encontrar la instancia"""
        nombre = str(row.get('nombre') or '').strip()
        padre_id = row.get('padre_id_fast')
        
        pk = self.instance_map.get((nombre, padre_id))
        if pk:
            try:
                return self._meta.model(pk=pk)
            except Exception:
                return None
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
    list_select_related = ('marca',)
    search_fields = ('nombre', 'marca__nombre')
    readonly_fields = ('lista_activos_ubicacion',)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(activos_count=Count('activos'))

    def total_activos(self, obj):
        return getattr(obj, 'activos_count', obj.activos.count())
    total_activos.short_description = 'Total Activos'
    total_activos.admin_order_field = 'activos_count'

    def lista_activos_ubicacion(self, obj):
        activos = obj.activos.select_related('ubicacion').order_by('ubicacion__nombre')
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
class UbicacionAdmin(ImportExportMixin, admin.ModelAdmin):
    """
    Admin para ubicaciones jerárquicas con estructura simple.
    """
    resource_class = UbicacionResource
    list_display = ('nombre', 'padre', 'orden', 'descripcion')
    list_editable = ('orden',)
    search_fields = ('nombre',)
    list_filter = ('padre',)
    autocomplete_fields = ('padre',)


class ActivoResource(resources.ModelResource):
    modelo_nombre = fields.Field(
        column_name='modelo_nombre',
        attribute='modelo',
        widget=ForeignKeyWidget(Modelo, field='nombre')
    )
    categoria_nombre = fields.Field(
        column_name='categoria_nombre',
        attribute='categoria',
        widget=ForeignKeyWidget(Categoria, field='nombre')
    )
    ubicacion_nombre = fields.Field(
        column_name='ubicacion_nombre',
        attribute='ubicacion',
        widget=ForeignKeyWidget(Ubicacion, field='nombre')
    )
    responsable_username = fields.Field(
        column_name='responsable_username',
        attribute='responsable',
        widget=ForeignKeyWidget(User, field='username')
    )

    class Meta:
        model = Activo
        fields = ('id', 'nombre', 'codigo_interno', 'serie', 'modelo_nombre', 'categoria_nombre', 'estado', 'ubicacion_nombre', 'responsable_username')
        export_order = ('id', 'codigo_interno', 'nombre', 'serie', 'modelo_nombre', 'categoria_nombre', 'estado', 'ubicacion_nombre', 'responsable_username')
        skip_unchanged = True
        report_skipped = True
        use_bulk = True
        batch_size = 1000

@admin.register(Activo)
class ActivoAdmin(ImportExportMixin, admin.ModelAdmin):
    resource_class = ActivoResource
    list_display = ('codigo_interno', 'nombre', 'get_marca', 'modelo', 'serie', 'categoria', 'estado', 'ubicacion', 'responsable')
    list_filter = ('estado', 'categoria', 'modelo__marca', 'creado_en', 'ubicacion')
    list_select_related = ('modelo__marca', 'categoria', 'ubicacion', 'responsable')
    search_fields = ('nombre', 'codigo_interno', 'serie', 'modelo__marca__nombre', 'modelo__nombre', 'marca_legacy', 'modelo_legacy', 'ubicacion__nombre', 'ubicacion_legacy')
    autocomplete_fields = ('modelo', 'categoria', 'ubicacion', 'responsable')
    readonly_fields = ('creado_en', 'actualizado_en', 'ver_en_plano')

    def changelist_view(self, request, extra_context=None):
        if request.GET.get('_popup'):
            from .models import Ubicacion, Activo
            
            # Obtener todas las ubicaciones en orden alfabético (MPTT removido)
            ubicaciones = Ubicacion.objects.all().order_by('nombre')
            
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
