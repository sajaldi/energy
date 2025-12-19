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
    list_display = ('nombre', 'descripcion')
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
        # Para IMPORTAR solo necesitas: nombre, padre_nombre, descripcion
        # Para EXPORTAR obtienes además: clave_unica, ruta_completa
        fields = ('id', 'nombre', 'padre_nombre', 'descripcion', 'ruta_completa', 'clave_unica')
        export_order = ('id', 'clave_unica', 'ruta_completa', 'nombre', 'padre_nombre', 'descripcion')
        # No usamos import_id_fields - dejamos que busque por nombre+padre
        skip_unchanged = True
        report_skipped = True
    
    def get_instance(self, instance_loader, row):
        """
        Busca la ubicación existente por la combinación de nombre + padre.
        Esto permite tener múltiples "Nivel 1" en diferentes torres.
        """
        try:
            nombre = row.get('nombre', '').strip()
            padre_nombre = row.get('padre_nombre', '').strip()
            
            if not nombre:
                return None
            
            # Buscar el padre si se especificó
            padre = None
            if padre_nombre:
                try:
                    # Buscar padre - puede haber múltiples con el mismo nombre,
                    # tomamos el primero (idealmente no debería haber ambigüedad)
                    padre = Ubicacion.objects.filter(nombre=padre_nombre).first()
                except Ubicacion.DoesNotExist:
                    return None
            
            # Buscar ubicación por nombre + padre
            if padre:
                return Ubicacion.objects.filter(nombre=nombre, padre=padre).first()
            else:
                # Buscar ubicación raíz (sin padre)
                return Ubicacion.objects.filter(nombre=nombre, padre__isnull=True).first()
                
        except Exception:
            pass
        
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
    list_display = ('nombre', 'marca')
    list_filter = ('marca',)
    search_fields = ('nombre', 'marca__nombre')

@admin.register(Ubicacion)
class UbicacionAdmin(ImportExportModelAdmin, DraggableMPTTAdmin):
    """
    Admin que combina la funcionalidad de drag-and-drop de MPTT 
    con la capacidad de import/export de django-import-export.
    """
    resource_class = UbicacionResource
    mptt_indent_field = "nombre"
    list_display = ('tree_actions', 'indented_title', 'descripcion')
    list_display_links = ('indented_title',)
    search_fields = ('nombre',)
    list_filter = ('padre',)

@admin.register(Activo)
class ActivoAdmin(ImportExportModelAdmin):
    list_display = ('codigo_interno', 'nombre', 'get_marca', 'modelo', 'serie', 'categoria', 'estado', 'ubicacion', 'responsable')
    list_filter = ('estado', 'categoria', 'modelo__marca', 'creado_en', 'ubicacion')
    search_fields = ('nombre', 'codigo_interno', 'serie', 'modelo__marca__nombre', 'modelo__nombre', 'marca_legacy', 'modelo_legacy', 'ubicacion__nombre', 'ubicacion_legacy')
    readonly_fields = ('creado_en', 'actualizado_en', 'ver_en_plano')
    
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
