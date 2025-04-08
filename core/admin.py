from django.contrib import admin
from django.utils.safestring import mark_safe
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from .models import (
    Consumo, Medidor, PuntoMedicion, Equipo,
    CaracteristicaMedicion, CategoriaPuntoMedicion, DocumentoMedicion, RangoMedicion
)
from . import views  # Add this import at the top

# Fix the resource first
class ConsumoResource(resources.ModelResource):
    class Meta:
        model = Consumo
        fields = ('fecha', 'consumo', 'medidor')
        import_id_fields = ()
        skip_unchanged = True
        report_skipped = False
        unique_together = ('fecha', 'medidor')

# Custom admin class to fix the log entry error
class FixedImportExportAdmin(ImportExportModelAdmin):
    def _create_log_entry(self, request, row, instance, new, **kwargs):
        from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
        from django.contrib.contenttypes.models import ContentType
        
        LogEntry.objects.log_action(
            user_id=getattr(request.user, 'pk', None),
            content_type_id=ContentType.objects.get_for_model(self.model).pk,
            object_id=instance.pk,
            object_repr=str(instance),
            action_flag=ADDITION if new else CHANGE,
            change_message="Import completed via admin"
        )

@admin.register(Medidor)
class MedidorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo']
    list_filter = ['tipo']
    search_fields = ['nombre']
    list_editable = ['tipo']  # Makes tipo editable in list view

@admin.register(Consumo)
class ConsumoAdmin(FixedImportExportAdmin):
    resource_class = ConsumoResource
    list_display = ['fecha', 'consumo', 'medidor1', 'medidor']  # Show both fields
    list_filter = ['fecha', 'medidor']
    raw_id_fields = ['medidor1']  # Better for large datasets
    date_hierarchy = 'fecha'
    import_export_formats = ['csv', 'xls', 'xlsx', 'json']
    
    def get_urls(self) -> list:
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('import-excel/', self.admin_site.admin_view(views.import_excel),  # Changed to views.import_excel
                 name='import_consumo'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_url'] = 'admin:import_consumo'
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ('numero_equipo', 'descripcion')
    list_filter = ('numero_equipo',)
    search_fields = ('numero_equipo', 'descripcion')
    ordering = ('numero_equipo',)
class RangoMedicionInline(admin.TabularInline):
    model = RangoMedicion
    extra = 1
    fields = ('descripcion', 'valor_min', 'valor_max', 'color')

@admin.register(CaracteristicaMedicion)
class CaracteristicaMedicionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'unidad_medida', 'descripcion')
    search_fields = ('nombre', 'unidad_medida')
    list_filter = ('unidad_medida',)
    ordering = ('nombre',)
    inlines = [RangoMedicionInline]

@admin.register(RangoMedicion)
class RangoMedicionAdmin(admin.ModelAdmin):
    list_display = ('colored_name', 'caracteristica', 'valor_min', 'valor_max')
    list_filter = ('caracteristica',)
    search_fields = ('descripcion',)
    
    def colored_name(self, obj):
        return mark_safe(f'<span style="color: {obj.color};">■</span> {obj.descripcion}')
        colored_name.short_description = 'Rango'  # Fixed indentation

@admin.register(DocumentoMedicion)
class DocumentoMedicionAdmin(admin.ModelAdmin):
    list_display = ('punto_medicion', 'fecha_hora_lectura', 'valor_leido', 'get_rango_display', 'lectura_contador')
    list_filter = ('punto_medicion',)
    raw_id_fields = ('punto_medicion',)
    date_hierarchy = 'fecha_hora_lectura'
    ordering = ('-fecha_hora_lectura',)
    search_fields = ('observaciones',)
    
    def get_rango_display(self, obj):
        """Determine and display the applicable range based on the measurement value."""
        if not obj.valor_leido or not obj.punto_medicion or not obj.punto_medicion.caracteristica:
            return "-"
        
        # Find the appropriate range for this value
        rangos = RangoMedicion._default_manager.filter(
            caracteristica=obj.punto_medicion.caracteristica,
            valor_min__lte=obj.valor_leido,
            valor_max__gte=obj.valor_leido
        ).first()
        
        if rangos:
            return mark_safe(f'<span style="color: {rangos.color};">■</span> {rangos.descripcion}')
        return "Fuera de rango"
        get_rango_display.short_description = "Rango"  # Fixed indentation
        get_rango_display.admin_order_field = 'valor_leido'  # Fixed indentation

# Remove the existing PuntoMedicion registration and add proper admin
# admin.site.unregister(PuntoMedicion)  # Remove this line

@admin.register(PuntoMedicion)
class PuntoMedicionAdmin(admin.ModelAdmin):
    list_display = ('numero_interno', 'descripcion', 'objeto_tecnico_equipo', 'categoria', 'caracteristica')
    list_filter = ('categoria', 'es_contador')
    search_fields = ('descripcion', 'numero_interno')
    raw_id_fields = ('objeto_tecnico_equipo', 'objeto_tecnico_ubicacion')
    list_select_related = ('categoria', 'caracteristica')