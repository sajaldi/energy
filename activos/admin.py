from django.db import models
from django.contrib import admin, messages
from django.http import HttpResponse
from django.db.models import Count
from import_export.admin import ImportExportModelAdmin, ImportExportMixin, ImportExportActionModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from django.contrib.auth.models import User
from .models import Activo, Categoria, Ubicacion, Marca, Modelo, Plano, VisorPlano, PinPlano

# ... (resto de registros)

from django.utils.html import format_html
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME

@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ubicacion', 'documento_info', 'visualizar_archivo', 'creado_en')
    list_filter = ('ubicacion',)
    list_select_related = ('ubicacion', 'documento__ultima_revision')
    search_fields = ('nombre', 'ubicacion__nombre', 'documento__codigo')
    filter_horizontal = ('activos',)
    autocomplete_fields = ('documento',)
    readonly_fields = ('visualizar_archivo',)
    fieldsets = (
        (None, {'fields': ('nombre', 'ubicacion', 'descripcion')}),
        ('Archivo del Plano', {
            'fields': ('documento', 'archivo'),
            'description': 'Usa "Documento" para control de versiones, o "Archivo" para carga directa.'
        }),
        ('Activos Vinculados', {'fields': ('activos',)}),
    )

    def documento_info(self, obj):
        if obj.documento:
            rev = obj.revision_actual or ''
            return format_html('<span style="color: #2563eb;">{}</span> <small style="color: #64748b;">{}</small>', 
                             obj.documento.codigo, rev)
        return format_html('<span style="color: #94a3b8;">Sin documento</span>')
    documento_info.short_description = "Documento"

    def visualizar_archivo(self, obj):
        archivo = obj.archivo_actual
        if archivo:
            rev_tag = f' ({obj.revision_actual})' if obj.revision_actual else ''
            return format_html('<a href="{0}" target="_blank">📄 Ver Plano{1}</a>', archivo.url, rev_tag)
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
        fields = ('id', 'clave_unica', 'ruta_completa', 'nombre', 'tipo', 'padre_nombre', 'orden', 'descripcion')
        export_order = ('id', 'clave_unica', 'ruta_completa', 'nombre', 'tipo', 'padre_nombre', 'orden', 'descripcion')
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
    categoria_nombre = fields.Field(
        column_name='categoria_nombre',
        attribute='categoria',
        widget=ForeignKeyWidget(Categoria, field='nombre')
    )

    class Meta:
        model = Modelo
        # Identificamos por nombre y marca para que si el ID está vacío, 
        # actualice si ya existe esa combinación o cree uno nuevo si no.
        import_id_fields = ('nombre', 'marca_nombre')
        fields = ('id', 'nombre', 'marca_nombre', 'categoria_nombre')
        export_order = ('id', 'nombre', 'marca_nombre', 'categoria_nombre')

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
    list_display = ('nombre', 'marca', 'categoria', 'total_activos')
    list_filter = ('marca', 'categoria')
    list_select_related = ('marca', 'categoria')
    autocomplete_fields = ('marca', 'categoria')

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}
    
    def get_export_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}
    search_fields = ('nombre', 'marca__nombre')
    readonly_fields = ('lista_activos_ubicacion', 'rutinas_aplicables')

    def rutinas_aplicables(self, obj):
        if not obj.categoria:
            return format_html('<span style="color: #94a3b8; font-style: italic;">No hay una categoría de activo definida para este modelo.</span>')
        
        # Buscar la categoría de mantenimiento vinculada (a través de la relación inversa)
        m_cat = getattr(obj.categoria, 'mantenimiento_categoria', None)
        
        if not m_cat:
            return format_html('<span style="color: #94a3b8; font-style: italic;">La categoría "{0}" no tiene una categoría de mantenimiento vinculada.</span>', obj.categoria.nombre)

        from mantenimiento.models import Rutina
        # Obtener ancestros de la categoría de mantenimiento vinculada para incluir rutinas generales
        m_cats_ids = []
        curr = m_cat
        while curr:
            m_cats_ids.append(curr.id)
            curr = curr.padre
            
        rutinas = Rutina.objects.filter(categoria_id__in=m_cats_ids).select_related('frecuencia', 'categoria')
        
        if not rutinas.exists():
            return format_html('<span style="color: #94a3b8; font-style: italic;">No hay rutinas de mantenimiento configuradas para la categoría "{0}".</span>', obj.categoria.nombre)
            
        html = '<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-top: 10px;">'
        html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        html += '<thead style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">'
        html += '<tr>'
        html += '<th style="text-align: left; padding: 12px 15px; color: #475569; font-weight: 700;">Rutina</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Frecuencia</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">HH/Técnicos</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Acción</th>'
        html += '</tr></thead><tbody>'
        
        for r in rutinas:
            frec_nombre = r.frecuencia.nombre if r.frecuencia else "N/A"
            hh = r.tiempo_estimado if r.tiempo_estimado else "---"
            tecs = r.cantidad_tecnicos
            
            html += f'<tr style="border-bottom: 1px solid #f1f5f9;">'
            html += f'<td style="padding: 12px 15px;">'
            html += f'<div style="font-weight: 600; color: #1e293b;">{r.nombre}</div>'
            html += f'<div style="font-size: 0.75rem; color: #64748b;">{r.categoria.nombre if r.categoria else "General"}</div>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<span style="background: #eff6ff; color: #2563eb; padding: 4px 10px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">{frec_nombre}</span>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center; color: #475569;">'
            html += f'{hh} <br> <small style="color: #94a3b8;">({tecs} Tec.)</small>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<a href="/admin/mantenimiento/rutina/{r.id}/change/" target="_blank" style="background: #f1f5f9; color: #475569; padding: 5px; border-radius: 4px; display: inline-flex; align-items: center; border: 1px solid #e2e8f0; text-decoration: none;">'
            html += f'<ion-icon name="open-outline" style="font-size: 1rem;"></ion-icon>'
            html += '</a></td></tr>'
        
        html += '</tbody></table></div>'
        return format_html(html)

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
            'fields': ('nombre', 'marca', 'categoria')
        }),
        ('Mantenimiento Preventivo Sugerido', {
            'fields': ('rutinas_aplicables',),
            'description': 'Listado de rutinas que aplican a todos los activos de este modelo basándose en su categoría.'
        }),
        ('Distribución de Activos', {
            'fields': ('lista_activos_ubicacion',),
            'description': 'Listado completo de equipos físicos asociados a este modelo, organizados jerárquicamente por su ubicación.'
        }),
    )


class UbicacionHijaInline(admin.TabularInline):
    model = Ubicacion
    fk_name = 'padre'
    extra = 1
    verbose_name = "Sub-Ubicación"
    verbose_name_plural = "Sub-Ubicaciones (Niveles Hijos)"
    fields = ('render_icon', 'nombre', 'orden', 'total_count', 'descripcion')
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
        count = obj.activos.count()
        if count == 0:
            return format_html('<span style="color: #cbd5e1; font-size: 0.75rem;">Vacío</span>')
        return format_html(
            '<div style="background: #eff6ff; color: #2563eb; padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 0.7rem; display: inline-block; border: 1px solid #dbeafe;">'
            '{} EQUIPOS'
            '</div>', count
        )
    total_count.short_description = 'Equipos'

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

@admin.register(Ubicacion)
class UbicacionAdmin(ImportExportMixin, admin.ModelAdmin):
    """
    Admin para ubicaciones jerárquicas con estructura premium.
    """
    resource_class = UbicacionResource
    list_display = ('nombre_con_indentacion', 'tipo', 'padre', 'orden', 'total_hijos', 'total_activos')
    list_display_links = ('nombre_con_indentacion',)
    list_editable = ('orden', 'tipo')
    search_fields = ('nombre',)
    list_filter = ('tipo', 'padre',)
    autocomplete_fields = ('padre',)
    inlines = [UbicacionHijaInline]

    class Media:
        css = {
            'all': (
                'https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap',
                # CSS inyectado para ajustar anchos de columnas del inline
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css',
            )
        }
        js = ('https://unpkg.com/ionicons@5.5.2/dist/ionicons/ionicons.esm.js', 
              'https://unpkg.com/ionicons@5.5.2/dist/ionicons/ionicons.js')

    # Añadimos un pequeño hack de CSS inline para el admin
    def get_inline_instances(self, request, obj=None):
        from django.utils.safestring import mark_safe
        # Inyectamos estilos directamente en el encabezado mediante un truco de admin
        # para forzar anchos de tabla del inline
        request._inline_css = mark_safe("""
            <style>
                .inline-group .tabular td.column-render_icon { width: 50px !important; text-align: center; }
                .inline-group .tabular td.column-orden { width: 80px !important; }
                .inline-group .tabular td.column-total_count { width: 120px !important; white-space: nowrap; }
                .inline-group .tabular td.column-nombre { width: 300px !important; }
                .inline-group fieldset { border: none !important; border-top: 1px solid #eee !important; }
            </style>
        """)
        return super().get_inline_instances(request, obj)

    def nombre_con_indentacion(self, obj):
        level = obj.level
        indent = level * 20
        icon = "🏢" if level == 0 else "↳"
        color = "#1e293b" if level == 0 else "#64748b"
        weight = "700" if level == 0 else "400"
        
        return format_html(
            '<div style="text-indent: {0}px; color: {1}; font-weight: {2}; display: flex; align-items: center;">'
            '<span style="margin-right: 8px; opacity: 0.6; font-style: normal;">{3}</span> {4}'
            '</div>',
            indent, color, weight, icon, obj.nombre
        )
    nombre_con_indentacion.short_description = 'Ubicación'

    def total_hijos(self, obj):
        count = obj.sub_ubicaciones.count()
        if count == 0:
            return format_html('<span style="color: #cbd5e1; font-size: 0.8rem;">Vacio</span>')
        return format_html('<span style="background: #f1f5f9; color: #475569; padding: 2px 10px; border-radius: 12px; font-weight: 700; font-size: 0.75rem;">{} sub-niveles</span>', count)
    total_hijos.short_description = 'Estructura'

    def total_activos(self, obj):
        # Contar activos en esta ubicación y todas sus descendientes
        from .models import Activo
        ubicaciones_ids = obj.get_descendants().values_list('id', flat=True)
        total = Activo.objects.filter(ubicacion_id__in=ubicaciones_ids).count()
        
        if total == 0:
            return format_html('<span style="color: #cbd5e1; font-size: 0.8rem;">Sin equipos</span>')
        return format_html('<span style="background: #eff6ff; color: #1d4ed8; padding: 2px 10px; border-radius: 12px; font-weight: 700; font-size: 0.75rem;">{} equipos</span>', total)
    total_activos.short_description = 'Carga de Activos'


class SmartUbicacionWidget(ForeignKeyWidget):
    """
    Widget optimizado que utiliza el caché del Resource para evitar consultas N+1.
    """
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        
        value_str = str(value).strip()
        resource = kwargs.get('resource')
        
        # 1. Normalizar separadores comunes
        normalized_val = value_str.replace(' → ', '|').replace(' -> ', '|').replace(' > ', '|')
        
        # 2. Intentar resolver por Clave Única (Ruta Completa) desde caché
        if resource and hasattr(resource, 'ubicacion_clave_cache'):
            if normalized_val in resource.ubicacion_clave_cache:
                return resource.ubicacion_clave_cache[normalized_val]
        
        # 3. Intentar resolver por Nombre Simple (solo si es único) desde caché
        if resource and hasattr(resource, 'ubicacion_nombre_cache'):
            if value_str in resource.ubicacion_nombre_cache:
                return resource.ubicacion_nombre_cache[value_str]

        # 4. Fallback: Resolución manual si el caché no lo tiene o el valor tiene jerarquía
        if '|' in normalized_val:
            parts = [p.strip() for p in normalized_val.split('|')]
            nombre_final = parts[-1]
            candidatos = Ubicacion.objects.filter(nombre__iexact=nombre_final)
            for cand in candidatos:
                if cand.get_clave_unica() == normalized_val:
                    return cand
        
        # Si llegamos aquí y hay jerarquía pero no se encontró, o no hay jerarquía...
        # Intentamos buscar en el caché de nombres (ya normalizado a iexact implícitamente por el diccionario si lo hiciéramos así)
        # Pero como fallback final, si no está en caché, hacemos una sola consulta
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
        attribute='modelo__categoria',
        widget=ForeignKeyWidget(Categoria, field='nombre'),
        readonly=True
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
        batch_size = 1000  # Optimizado: más registros por lote
        use_transactions = True  # Atomicidad para evitar estados inconsistentes

    def get_queryset(self, request):
        """Eager loading para que skip_row y exportación sean rápidos"""
        return super().get_queryset(request).select_related(
            'modelo__marca', 'modelo__categoria', 'ubicacion', 'responsable'
        )

    def get_bulk_update_fields(self):
        """Mapea nombres de campos del Resource a atributos reales del Modelo para Bulk Update"""
        actual_fields = {f.name for f in self._meta.model._meta.get_fields()}
        resource_fields = self.get_fields()
        
        update_fields = set()
        for f_name in super().get_bulk_update_fields():
            # Buscar el campo en el resource para ver qué atributo de modelo impacta
            res_field = next((rf for rf in resource_fields if rf.attribute and rf.column_name == f_name or rf.attribute == f_name), None)
            
            attr = res_field.attribute if res_field else f_name
            # Manejar atributos anidados (ej: modelo__nombre -> solo nos interesa 'modelo')
            base_attr = attr.split('__')[0] if attr else None
            
            if base_attr in actual_fields and base_attr != 'id':
                update_fields.add(base_attr)
                
        return list(update_fields)

    def skip_row(self, instance, original, row, import_validation_errors=None, **kwargs):
        """Lógica inteligente para decidir si omitir o no una fila"""
        # 1. Ignorar filas vacías o sin identificador
        if not any(row.values()):
            return True
        if not str(row.get('nombre') or '').strip() and not str(row.get('codigo_interno') or '').strip():
            return True

        # 2. Forzar actualización si cambió el modelo (indirecto)
        excel_model = str(row.get('modelo_nombre') or '').strip().upper()
        current_model = original.modelo.nombre.upper() if original and original.modelo else ''
        if excel_model and excel_model != current_model:
            return False
            
        # 3. Forzar actualización si cambió la categoría (indirecto via modelo)
        excel_cat = str(row.get('categoria_nombre') or '').strip().upper()
        current_cat = original.modelo.categoria.nombre.upper() if original and original.modelo and original.modelo.categoria else ''
        if excel_cat and excel_cat != current_cat:
            return False
            
        return super().skip_row(instance, original, row, import_validation_errors, **kwargs)

    def before_import(self, dataset, *args, **kwargs):
        """Precarga cachés para velocidad y precisión en jerarquías"""
        from django.core.cache import cache
        from .models import Marca, Modelo, Categoria, Ubicacion
        from django.db.models import Count
        
        # 0. Inicializar progreso detallado
        user = kwargs.get('user')
        self._import_user = user
        if user:
            cache.set(f"import_progress_{user.id}", 0, 600)
            cache.set(f"import_progress_{user.id}_count", 0, 600)
            cache.set(f"import_progress_{user.id}_current", 'Preparando datos...', 600)
            cache.set(f"import_progress_{user.id}_stats", {'new': 0, 'update': 0, 'skip': 0, 'error': 0}, 600)
            cache.set(f"import_progress_{user.id}_start", __import__('time').time(), 600)
            self.total_rows = len(dataset)

        # 1. Caché Ubicaciones
        self.ubicacion_clave_cache = {}
        self.ubicacion_nombre_cache = {}
        
        # Identificar nombres duplicados para evitar ambigüedad en el caché simple
        nombres_duplicados = set(
            Ubicacion.objects.values('nombre')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
            .values_list('nombre', flat=True)
        )
        
        for loc in Ubicacion.objects.all().select_related('padre'):
            # Siempre cacheamos la ruta completa (jerarquía)
            self.ubicacion_clave_cache[loc.get_clave_unica()] = loc
            
            # Solo cacheamos el nombre simple si NO es un nombre ambiguo (duplicado)
            if loc.nombre not in nombres_duplicados:
                self.ubicacion_nombre_cache[loc.nombre] = loc
        
        self.fields['ubicacion_nombre'].widget.resource = self

        # 2. Caché Marcas/Modelos/Categorías
        self.marca_cache = {m.nombre.upper(): m for m in Marca.objects.all()}
        self.modelo_cache = {m.nombre.upper(): m for m in Modelo.objects.all().select_related('marca', 'categoria')}
        self.categoria_cache = {c.nombre.upper(): c for c in Categoria.objects.all()}

        # 3. Caché Activos por Código Interno (para get_instance instantáneo)
        self.activo_cache = {a.codigo_interno: a for a in Activo.objects.all().only('id', 'codigo_interno') if a.codigo_interno}

    def after_import_row(self, row, row_result, **kwargs):
        """Actualizar progreso detallado en caché para seguimiento en tiempo real"""
        from django.core.cache import cache
        user = kwargs.get('user')
        if user and hasattr(self, 'total_rows') and self.total_rows > 0:
            uid = user.id
            current = cache.get(f"import_progress_{uid}_count", 0) + 1
            cache.set(f"import_progress_{uid}_count", current, 600)
            
            percent = min(int((current / self.total_rows) * 100), 100)
            cache.set(f"import_progress_{uid}", percent, 600)
            
            # Nombre del activo actual para mostrar en UI
            current_name = row.get('nombre') or row.get('codigo_interno') or f'Fila {current}'
            cache.set(f"import_progress_{uid}_current", str(current_name)[:50], 600)
            
            # Acumular estadísticas por tipo de operación
            stats = cache.get(f"import_progress_{uid}_stats", {'new': 0, 'update': 0, 'skip': 0, 'error': 0})
            import_type = getattr(row_result, 'import_type', None)
            if import_type == 'new':
                stats['new'] += 1
            elif import_type == 'update':
                stats['update'] += 1
            elif import_type == 'skip':
                stats['skip'] += 1
            if row_result.errors:
                stats['error'] += 1
            cache.set(f"import_progress_{uid}_stats", stats, 600)

    def dehydrate_ubicacion_nombre(self, activo):
        """Exportar la ruta completa para evitar ambigüedad en futuras importaciones"""
        if activo.ubicacion:
            return activo.ubicacion.get_ruta_completa()
        return ""

    def before_import_row(self, row, **kwargs):
        """Auto-creación inteligente de Marcas, Modelos y asignación de Categoría"""
        from .models import Marca, Modelo, Categoria
        
        mod_name = str(row.get('modelo_nombre') or '').strip()
        mar_name = str(row.get('marca_nombre') or '').strip()
        cat_name = str(row.get('categoria_nombre') or '').strip()
        
        if mod_name:
            mod_key = mod_name.upper()
            mar_key = mar_name.upper()
            
            # 1. Garantizar Marca
            marca_obj = self.marca_cache.get(mar_key) if mar_name else self.marca_cache.get("GENERICO")
            if not marca_obj:
                marca_obj, _ = Marca.objects.get_or_create(nombre=mar_name or "GENERICO")
                self.marca_cache[mar_key or "GENERICO"] = marca_obj
            
            # 2. Garantizar Categoría
            cat_obj = self.categoria_cache.get(cat_name.upper()) if cat_name else None
            if cat_name and not cat_obj:
                cat_obj, _ = Categoria.objects.get_or_create(nombre=cat_name)
                self.categoria_cache[cat_name.upper()] = cat_obj
            
            # 3. Garantizar Modelo
            mod_obj = self.modelo_cache.get(mod_key)
            if not mod_obj:
                mod_obj, _ = Modelo.objects.get_or_create(
                    nombre=mod_name, 
                    marca=marca_obj,
                    defaults={'categoria': cat_obj}
                )
                self.modelo_cache[mod_key] = mod_obj
            
            # Si ya existía pero tenemos categoría nueva/distinta, actualizamos solo si es necesario
            if cat_obj and mod_obj.categoria != cat_obj:
                mod_obj.categoria = cat_obj
                mod_obj.save()

    def get_instance(self, instance_loader, row):
        codigo = row.get('codigo_interno')
        if codigo:
            # Usar caché local en lugar de consultar la DB
            if hasattr(self, 'activo_cache'):
                return self.activo_cache.get(codigo)
            return self._meta.model.objects.filter(codigo_interno=codigo).first()
        return None

class ActivoFaltantesFilter(admin.SimpleListFilter):
    title = 'Calidad de Datos'
    parameter_name = 'faltante'

    def lookups(self, request, model_admin):
        return (
            ('serie', '❌ Sin N° Serie'),
            ('responsable', '👤 Sin Responsable'),
            ('ubicacion', '📍 Sin Ubicación'),
            ('codigo', '🆔 Sin Código Interno'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'serie':
            return queryset.filter(models.Q(serie__isnull=True) | models.Q(serie=''))
        if self.value() == 'responsable':
            return queryset.filter(responsable__isnull=True)
        if self.value() == 'ubicacion':
            return queryset.filter(ubicacion__isnull=True)
        if self.value() == 'codigo':
            return queryset.filter(models.Q(codigo_interno__isnull=True) | models.Q(codigo_interno=''))
        return queryset

class UbicacionHierarchyFilter(admin.SimpleListFilter):
    title = 'Ubicación'
    parameter_name = 'ubicacion_id'

    def lookups(self, request, model_admin):
        # 1. Opción para activos sin ubicación
        lookups = [('none', '📍 Sin Ubicación Asignada')]
        
        # 2. Todas las ubicaciones ordenadas
        from .models import Ubicacion
        locations = Ubicacion.objects.all().order_by('nombre')
        for loc in locations:
            lookups.append((loc.id, loc.ruta_completa))
            
        return lookups

    def queryset(self, request, queryset):
        val = self.value()
        if val:
            if val == 'none':
                return queryset.filter(ubicacion__isnull=True)
            
            from .models import Ubicacion
            try:
                ubicacion = Ubicacion.objects.get(id=val)
                # Obtener todos los descendientes incluyendo el actual
                descendientes_ids = ubicacion.get_descendants(include_self=True).values_list('id', flat=True)
                return queryset.filter(ubicacion_id__in=descendientes_ids)
            except (Ubicacion.DoesNotExist, ValueError):
                return queryset
        return queryset

@admin.register(Activo)
class ActivoAdmin(ImportExportActionModelAdmin):
    resource_class = ActivoResource

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}
    
    def get_export_resource_kwargs(self, request, *args, **kwargs):
        return {'user': request.user}

    list_display = ('codigo_interno', 'nombre', 'get_marca', 'modelo', 'serie', 'get_categoria', 'estado', 'ubicacion', 'responsable')
    list_filter = (ActivoFaltantesFilter, 'estado', 'modelo__categoria', 'modelo__marca', 'responsable', 'creado_en', UbicacionHierarchyFilter)
    list_select_related = ('modelo__marca', 'modelo__categoria', 'ubicacion', 'responsable')
    search_fields = ('nombre', 'codigo_interno', 'serie', 'modelo__marca__nombre', 'modelo__nombre', 'marca_legacy', 'modelo_legacy', 'ubicacion__nombre', 'ubicacion_legacy')
    autocomplete_fields = ('modelo', 'ubicacion', 'responsable')
    readonly_fields = ('creado_en', 'actualizado_en', 'ver_en_plano', 'rutinas_aplicables')
    actions = ['export_admin_action', 'export_direct_xlsx']

    def export_admin_action(self, request, queryset):
        """Redirección con descripción personalizada (2 pasos)"""
        return super().export_admin_action(request, queryset)
    export_admin_action.short_description = "Exportar activos seleccionados"

    @admin.action(description="⬇️ Descarga Directa Excel (Rápido)")
    def export_direct_xlsx(self, request, queryset):
        """Exportación en un solo paso (sin preguntar formato)"""
        try:
            # Usamos directamente la clase definida en el admin
            resource_class = self.resource_class
            resource_kwargs = self.get_export_resource_kwargs(request)
            resource = resource_class(**resource_kwargs)
            
            dataset = resource.export(queryset)
            response = HttpResponse(
                dataset.xlsx, 
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="activos_{queryset.count()}_items.xlsx"'
            return response
        except Exception as e:
            self.message_user(request, f"Error en exportación directa: {str(e)}", messages.ERROR)
            return None

    def rutinas_aplicables(self, obj):
        if not obj.modelo or not obj.modelo.categoria:
            return format_html('<span style="color: #94a3b8; font-style: italic;">No hay una categoría de activo definida para este modelo.</span>')
        
        # Buscar la categoría de mantenimiento vinculada
        m_cat = getattr(obj.modelo.categoria, 'mantenimiento_categoria', None)

        if not m_cat:
            return format_html('<span style="color: #94a3b8; font-style: italic;">La categoría "{0}" no tiene una categoría de mantenimiento vinculada.</span>', obj.modelo.categoria.nombre)

        from mantenimiento.models import Rutina
        # Obtener ancestros de la categoría de mantenimiento vinculada
        m_cats_ids = []
        curr = m_cat
        while curr:
            m_cats_ids.append(curr.id)
            curr = curr.padre
            
        rutinas = Rutina.objects.filter(categoria_id__in=m_cats_ids).select_related('frecuencia', 'categoria')
        
        if not rutinas.exists():
            return format_html('<span style="color: #94a3b8; font-style: italic;">No hay rutinas de mantenimiento configuradas para la categoría "{0}".</span>', obj.modelo.categoria.nombre)
            
        html = '<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-top: 10px;">'
        html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
        html += '<thead style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">'
        html += '<tr>'
        html += '<th style="text-align: left; padding: 12px 15px; color: #475569; font-weight: 700;">Rutina</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Frecuencia</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">HH/Técnicos</th>'
        html += '<th style="text-align: center; padding: 12px 15px; color: #475569; font-weight: 700;">Acción</th>'
        html += '</tr></thead><tbody>'
        
        for r in rutinas:
            frec_nombre = r.frecuencia.nombre if r.frecuencia else "N/A"
            hh = r.tiempo_estimado if r.tiempo_estimado else "---"
            tecs = r.cantidad_tecnicos
            
            html += f'<tr style="border-bottom: 1px solid #f1f5f9;">'
            html += f'<td style="padding: 12px 15px;">'
            html += f'<div style="font-weight: 600; color: #1e293b;">{r.nombre}</div>'
            html += f'<div style="font-size: 0.75rem; color: #64748b;">{r.categoria.nombre if r.categoria else "General"}</div>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<span style="background: #eff6ff; color: #2563eb; padding: 4px 10px; border-radius: 12px; font-weight: 600; font-size: 0.75rem;">{frec_nombre}</span>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center; color: #475569;">'
            html += f'{hh} <br> <small style="color: #94a3b8;">({tecs} Tec.)</small>'
            html += f'</td>'
            html += f'<td style="padding: 12px 15px; text-align: center;">'
            html += f'<a href="/admin/mantenimiento/rutina/{r.id}/change/" target="_blank" style="background: #f1f5f9; color: #475569; padding: 5px; border-radius: 4px; display: inline-flex; align-items: center; border: 1px solid #e2e8f0; text-decoration: none;">'
            html += f'<ion-icon name="open-outline" style="font-size: 1rem;"></ion-icon>'
            html += '</a></td></tr>'
        
        html += '</tbody></table></div>'
        return format_html(html)

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
                cat = activo.modelo.categoria if activo.modelo else None
                c_id = str(cat.id) if cat else "0"
                c_nombre = cat.nombre if cat else "Sin Categoría"
                
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
    
    def get_categoria(self, obj):
        if obj.modelo and obj.modelo.categoria:
            return obj.modelo.categoria
        return "---"
    get_categoria.short_description = 'Categoría'

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
            'fields': ('nombre', 'codigo_interno', 'serie')
        }),
        ('Detalles Técnicos', {
            'fields': ('modelo', 'marca_legacy', 'modelo_legacy', 'descripcion', 'foto')
        }),
        ('Estado y Ubicación', {
            'fields': ('estado', 'ubicacion', 'ubicacion_legacy', 'responsable', 'ver_en_plano')
        }),
        ('Mantenimiento Preventivo', {
            'fields': ('rutinas_aplicables',),
            'description': 'Rutinas de mantenimiento asociadas automáticamente según la categoría del modelo de este equipo.'
        }),
        ('Información Financiera', {
            'fields': ('fecha_compra', 'costo')
        }),
        ('Sistema', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )
