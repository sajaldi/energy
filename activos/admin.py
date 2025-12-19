from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from mptt.admin import DraggableMPTTAdmin
from .models import Activo, Categoria, Ubicacion, Marca, Modelo, Plano

# ... (resto de registros)

@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ubicacion', 'creado_en')
    list_filter = ('ubicacion',)
    search_fields = ('nombre', 'ubicacion__nombre')
    filter_horizontal = ('activos',)

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
    readonly_fields = ('creado_en', 'actualizado_en')
    
    def get_marca(self, obj):
        if obj.modelo:
            return obj.modelo.marca
        return obj.marca_legacy
    get_marca.short_description = 'Marca'

    fieldsets = (
        ('Identificación', {
            'fields': ('nombre', 'codigo_interno', 'serie', 'categoria')
        }),
        ('Detalles Técnicos', {
            'fields': ('modelo', 'marca_legacy', 'modelo_legacy', 'descripcion', 'foto')
        }),
        ('Estado y Ubicación', {
            'fields': ('estado', 'ubicacion', 'ubicacion_legacy', 'responsable')
        }),
        ('Información Financiera', {
            'fields': ('fecha_compra', 'costo')
        }),
        ('Sistema', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )
