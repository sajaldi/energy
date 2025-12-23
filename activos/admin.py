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
    Widget que busca el padre por nombre y devuelve el primero encontrado.
    Evita MultipleObjectsReturned en jerarquías con nombres repetidos en distintos niveles.
    """
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        return Ubicacion.objects.filter(nombre=value).first()

class UbicacionResource(resources.ModelResource):
    """
    Resource para Ubicaciones jerárquicas.
    Permite importar usando 'padre_nombre' en lugar de IDs.
    """
    padre_nombre = fields.Field(
        column_name='padre_nombre',
        attribute='padre',
        widget=SmartParentWidget(Ubicacion, field='nombre')
    )
    
    # Campos adicionales para exportación
    id = fields.Field(column_name='id', attribute='id', readonly=True)
    clave_unica = fields.Field(column_name='clave_unica', readonly=True)
    ruta_completa = fields.Field(column_name='ruta_completa', readonly=True)

    class Meta:
        model = Ubicacion
        # Usamos nombre y padre_nombre como identificadores para evitar duplicados en importación
        import_id_fields = ('nombre', 'padre_nombre')
        fields = ('id', 'clave_unica', 'ruta_completa', 'nombre', 'padre_nombre', 'orden', 'descripcion')
        export_order = ('id', 'clave_unica', 'ruta_completa', 'nombre', 'padre_nombre', 'orden', 'descripcion')
        skip_unchanged = True
        report_skipped = True
        
        # Desactivamos bulk para manejar la jerarquía fila a fila y evitar errores de bulk_update con PKs
        use_bulk = False

    def dehydrate_clave_unica(self, obj):
        return obj.get_clave_unica()

    def dehydrate_ruta_completa(self, obj):
        return obj.ruta_completa


class ModeloInline(admin.TabularInline):
    model = Modelo
    extra = 1

@admin.register(Marca)
class MarcaAdmin(ImportExportModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)
    inlines = [ModeloInline]

class ModeloResource(resources.ModelResource):
    marca_nombre = fields.Field(
        column_name='marca_nombre',
        attribute='marca',
        widget=ForeignKeyWidget(Marca, field='nombre')
    )

    class Meta:
        model = Modelo
        # Identificamos por nombre y marca para que si el ID está vacío, 
        # actualice si ya existe esa combinación o cree uno nuevo si no.
        import_id_fields = ('nombre', 'marca_nombre')
        fields = ('id', 'nombre', 'marca_nombre')
        export_order = ('id', 'nombre', 'marca_nombre')

    def skip_row(self, instance, original, row, import_validation_errors=None, **kwargs):
        if not any(row.values()): return True
        return super().skip_row(instance, original, row, import_validation_errors, **kwargs)

    def before_import_row(self, row, **kwargs):
        """Asegurar que la marca existe antes de importar el modelo"""
        marca_name = str(row.get('marca_nombre') or '').strip()
        if marca_name:
            from .models import Marca
            Marca.objects.get_or_create(nombre=marca_name)

@admin.register(Modelo)
class ModeloAdmin(ImportExportModelAdmin):
    resource_class = ModeloResource
    list_display = ('nombre', 'marca', 'total_activos')
    list_filter = ('marca',)
    list_select_related = ('marca',)

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}
    
    def get_export_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}
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


class SmartUbicacionWidget(ForeignKeyWidget):
    """
    Widget optimizado que utiliza el caché del Resource para evitar consultas N+1.
    """
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        
        value_str = str(value).strip()
        resource = kwargs.get('resource')
        
        # 1. Intentar resolver por Clave Única (Ruta con pipes o flechas) desde caché
        normalized_val = value_str.replace(' → ', '|')
        
        if resource and hasattr(resource, 'ubicacion_clave_cache'):
            if normalized_val in resource.ubicacion_clave_cache:
                return resource.ubicacion_clave_cache[normalized_val]
        
        # 2. Intentar resolver por Nombre Simple desde caché
        if resource and hasattr(resource, 'ubicacion_nombre_cache'):
            if value_str in resource.ubicacion_nombre_cache:
                return resource.ubicacion_nombre_cache[value_str]

        # 3. Fallback: Consulta directa
        parts = []
        if '|' in value_str:
            parts = [p.strip() for p in value_str.split('|')]
        elif '→' in value_str:
            parts = [p.strip() for p in value_str.split('→')]
            
        if parts:
            nombre_final = parts[-1]
            candidatos = Ubicacion.objects.filter(nombre__iexact=nombre_final)
            for cand in candidatos:
                if cand.get_clave_unica() == normalized_val or cand.get_ruta_completa() == value_str:
                    return cand
        
        return Ubicacion.objects.filter(nombre__iexact=value_str).first()

class ActivoResource(resources.ModelResource):
    marca_nombre = fields.Field(
        column_name='marca_nombre',
        attribute='modelo__marca__nombre',
        readonly=True
    )
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
        widget=SmartUbicacionWidget(Ubicacion, field='nombre')
    )
    responsable_username = fields.Field(
        column_name='responsable_username',
        attribute='responsable',
        widget=ForeignKeyWidget(User, field='username')
    )

    class Meta:
        model = Activo
        import_id_fields = ('codigo_interno',)
        fields = (
            'id', 'nombre', 'codigo_interno', 'serie', 'marca_nombre', 'modelo_nombre', 
            'categoria_nombre', 'estado', 'ubicacion_nombre', 'responsable_username',
            'descripcion', 'fecha_compra', 'costo', 'ubicacion_legacy'
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True
        use_bulk = True
        batch_size = 500

    def get_bulk_update_fields(self):
        """Evita Fallos con Campos Virtuales en Bulk Update"""
        actual_fields = [f.name for f in self._meta.model._meta.get_fields()]
        fields = super().get_bulk_update_fields()
        return [f for f in fields if f in actual_fields and f != 'id']

    def skip_row(self, instance, original, row, import_validation_errors=None, **kwargs):
        """Ignorar filas vacías"""
        if not any(row.values()):
            return True
        if not str(row.get('nombre') or '').strip() and not str(row.get('codigo_interno') or '').strip():
            return True
        return super().skip_row(instance, original, row, import_validation_errors, **kwargs)

    def before_import(self, dataset, *args, **kwargs):
        """Precarga cachés para velocidad y progreso"""
        from django.core.cache import cache
        from .models import Marca, Modelo, Categoria, Ubicacion
        
        # 0. Inicializar progreso
        user = kwargs.get('user')
        if user:
            cache.set(f"import_progress_{user.id}", 0, 300)
            cache.set(f"import_progress_{user.id}_count", 0, 300)
            self.total_rows = len(dataset)

        # 1. Caché Ubicaciones
        self.ubicacion_clave_cache = {}
        self.ubicacion_nombre_cache = {}
        for loc in Ubicacion.objects.all().select_related('padre'):
            self.ubicacion_clave_cache[loc.get_clave_unica()] = loc
            if loc.nombre not in self.ubicacion_nombre_cache:
                self.ubicacion_nombre_cache[loc.nombre] = loc
        self.fields['ubicacion_nombre'].widget.resource = self

        # 2. Caché Marcas/Modelos (Solo los nombres en mayúsculas para búsqueda rápida)
        self.marca_cache = {m.nombre.upper(): m for m in Marca.objects.all()}
        self.modelo_cache = {m.nombre.upper(): m for m in Modelo.objects.all().select_related('marca')}

    def after_import_row(self, row, row_result, **kwargs):
        """Actualizar progreso en caché"""
        from django.core.cache import cache
        user = kwargs.get('user')
        if user and hasattr(self, 'total_rows') and self.total_rows > 0:
            current = cache.get(f"import_progress_{user.id}_count", 0) + 1
            cache.set(f"import_progress_{user.id}_count", current, 300)
            percent = int((current / self.total_rows) * 100)
            # Asegurarse de no pasarnos de 100 si hay headers o filas extra
            if percent > 100: percent = 100
            cache.set(f"import_progress_{user.id}", percent, 300)

    def before_import_row(self, row, **kwargs):
        """Auto-creación inteligente de Marcas y Modelos"""
        from .models import Marca, Modelo
        
        mod_name = str(row.get('modelo_nombre') or '').strip()
        mar_name = str(row.get('marca_nombre') or '').strip()
        
        if mod_name:
            mod_key = mod_name.upper()
            mar_key = mar_name.upper()
            
            # Garantizar Marca
            marca_obj = None
            if mar_name:
                if mar_key not in self.marca_cache:
                    marca_obj, _ = Marca.objects.get_or_create(nombre=mar_name)
                    self.marca_cache[mar_key] = marca_obj
                else:
                    marca_obj = self.marca_cache[mar_key]
            
            # Garantizar Modelo
            if mod_key not in self.modelo_cache:
                if marca_obj:
                    mod_obj, _ = Modelo.objects.get_or_create(nombre=mod_name, marca=marca_obj)
                    self.modelo_cache[mod_key] = mod_obj
                else:
                    # Si no hay marca, buscamos una genérica o creamos el modelo sin ella (si fallara la DB diría)
                    # pero como 'marca' es NOT NULL, creamos una marca genérica "IMPORTADO" si es necesario
                    marca_gen, _ = Marca.objects.get_or_create(nombre="GENERICO")
                    mod_obj, _ = Modelo.objects.get_or_create(nombre=mod_name, marca=marca_gen)
                    self.modelo_cache[mod_key] = mod_obj

    def get_instance(self, instance_loader, row):
        codigo = row.get('codigo_interno')
        if codigo:
            return self._meta.model.objects.filter(codigo_interno=codigo).first()
        return None

@admin.register(Activo)
class ActivoAdmin(ImportExportModelAdmin):
    resource_class = ActivoResource

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}
    
    def get_export_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}

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
            # Restaurar la plantilla de importación/exportación si no es popup
            self.change_list_template = 'admin/import_export/change_list_import_export.html'
            
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
