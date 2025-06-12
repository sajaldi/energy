from django.contrib import admin
from django.utils.safestring import mark_safe
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin
from .models import (
    Consumo, InterfaceConsumo, Medidor, PuntoMedicion, Equipo,
    CaracteristicaMedicion, CategoriaPuntoMedicion, DocumentoMedicion, RangoMedicion, TipoMedidor, VistaConsumoDiferencia
)
from . import views
from datetime import datetime
from django.db import transaction


class ConsumoResource(resources.ModelResource):
    fecha = fields.Field(
        attribute='fecha',
        widget=widgets.DateTimeWidget(format='%m/%d/%Y %H:%M')
    )
    consumo = fields.Field(
        attribute='consumo',
        widget=widgets.FloatWidget()
    )
    medidor = fields.Field(
        attribute='medidor',
        column_name='medidor',
        widget=widgets.ForeignKeyWidget(Medidor, 'id')  # Cambia a 'nombre' si prefieres
    )

    class Meta:
        model = Consumo
        fields = ('fecha', 'consumo', 'medidor')
        import_id_fields = ('fecha', 'medidor')
        export_order = ('fecha', 'consumo', 'medidor')
        exclude = ('id',)
        skip_unknown = True
        use_transactions = True
        # skip_unchanged = False
        report_skipped = False

    def get_export_fields(self):
        fields = super().get_export_fields()
        print("Export fields:", [f.column_name for f in fields])
        return fields

    from django.db import transaction

    def before_import(self, dataset, using_transactions=True, dry_run=False, **kwargs):
        from tablib import Dataset
        import csv

        new_dataset = Dataset()
        new_dataset.headers = ['fecha', 'consumo', 'medidor']

        for row in dataset:
            if row and len(row) > 0:
                try:
                    # Detectar automáticamente el delimitador
                    sniffer = csv.Sniffer()
                    dialect = sniffer.sniff(row[0])
                    row = row[0].split(dialect.delimiter)
                except Exception as e:
                    print(f"Error detectando delimitador en la fila: {row} -> {e}")
                    continue

                print("Procesando fila:", row)
                if len(row) >= 3:
                    fecha, consumo, medidor = row[0].strip(), row[1].strip(), row[2].strip()

                    if not fecha or not medidor:
                        continue

                    try:
                        consumo = float(consumo.replace(',', '.'))  
                    except ValueError:
                        continue

                    try:
                        medidor_instance = Medidor.objects.get(id=medidor)
                    except Medidor.DoesNotExist:
                        continue

                    new_dataset.append([fecha, consumo, medidor_instance.id])

        if len(new_dataset) == 0:
            raise ValueError("No hay datos válidos para importar")

        dataset.wipe()
        for row in new_dataset:
            dataset.append(row)

        dataset.headers = ['fecha', 'consumo', 'medidor']

    def before_import_row(self, row, **kwargs):

        medidor_id = row.get('medidor') if isinstance(row, dict) else (row[2] if len(row) > 2 else None)
        if not Medidor.objects.filter(pk=medidor_id).exists():
            raise ValueError(f"Medidor con ID {medidor_id} no encontrado")
        
        consumo = row.get('consumo') if isinstance(row, dict) else (row[1] if len(row) > 1 else None)
        try:
            row['consumo'] = float(str(consumo).replace(';', '.'))
        except ValueError:
            raise ValueError(f"Consumo inválido: {consumo}")
        
    def save_instance(self, instance, *args, **kwargs):
        try:
            result = super().save_instance(instance, *args, **kwargs)
            medidor_id = instance.medidor.id if instance.medidor else None
            print(f"Instancia guardada: ID {instance.id}, Fecha {instance.fecha}, Medidor {medidor_id}")
            return result

        except Exception as e:
            print(f"Error al guardar: {e} - Fecha {instance.fecha}, Medidor {instance.medidor.id if instance.medidor else 'N/A'}")
            raise


    def after_import(self, dataset, result, using_transactions=True, dry_run=False, **kwargs):
        if not dry_run:
            pass

        if kwargs.get('request'):
            from django.contrib import messages
            new_rows = len(result.imported_rows) if hasattr(result, 'imported_rows') else 0
            updated_rows = len(result.updated_rows) if hasattr(result, 'updated_rows') else 0
            unchanged_rows = len(result.unchanged_rows) if hasattr(result, 'unchanged_rows') else 0

            messages.success(
                kwargs['request'],
                mark_safe(
                    f'<div style="color: green; font-weight: bold;">'
                    f'¡Datos importados correctamente!<br>'
                    f'Total de registros importados: {result.total_rows}<br>'
                    f'Registros nuevos: {new_rows}<br>'
                    f'Registros actualizados: {updated_rows}<br>'
                    f'Registros no modificados: {unchanged_rows} '
                    f'</div>'
                )
            )
class FixedImportExportAdmin(ImportExportModelAdmin):
    def _create_log_entry(self, request, row, instance, new, **kwargs):
        from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
        from django.contrib.contenttypes.models import ContentType

        if new or instance == 'new':
            return

        if isinstance(instance, str):
            try:
                instance_id = int(instance)
                instance = self.model.objects.get(pk=instance_id)
            except (ValueError, self.model.DoesNotExist):
                return

        user_id = request.user.pk if hasattr(request, 'user') and request.user.is_authenticated else None

        if hasattr(instance, 'pk') and instance.pk:
            LogEntry.objects.log_action(
                user_id=user_id,
                content_type_id=ContentType.objects.get_for_model(self.model).pk,
                object_id=instance.pk,
                object_repr=str(instance),
                action_flag=ADDITION if new else CHANGE,
                change_message="Import completed via admin"
            )
@admin.register(Consumo)
class ConsumoAdmin(FixedImportExportAdmin):
    resource_class = ConsumoResource
    list_display = ['id','fecha', 'consumo', 'medidor']
    list_filter = ['fecha', 'medidor']
    raw_id_fields = ['medidor']
    date_hierarchy = 'fecha'
    #paginas por defecto
    list_per_page = 10
    search_fields = ['id','medidor__nombre', 'consumo']
    def get_import_formats(self):
        from import_export.formats import base_formats
        return [base_formats.CSV]

    def get_export_formats(self):
        from import_export.formats import base_formats
        base_formats.CSV.DELIMITER = ';'
        base_formats.CSV.ENCODING = 'utf-8-sig'
        return [base_formats.CSV]

    def get_import_format_class(self, format):
        from import_export.formats import base_formats
        if format == 'csv':
            base_formats.CSV.DELIMITER = ';'
            base_formats.CSV.ENCODING = 'utf-8-sig'
            return base_formats.CSV
        return None

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('import-excel/', self.admin_site.admin_view(views.import_excel), name='import_consumo'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_url'] = 'admin:import_consumo'
        return super().changelist_view(request, extra_context=extra_context)

#Crea la admin class para el modelo TipoMedidor
@admin.register(TipoMedidor)
class TipoMedidorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion']
    search_fields = ['nombre']
    list_filter = ['nombre']
    ordering = ['nombre']
    list_per_page = 10
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('medidores')
    def medidores_count(self, obj):
        return obj.medidores.count()

#Inline para medidores hijos
class MedidorInline(admin.TabularInline):
    model = Medidor
    extra = 0
    fields = ['nombre', 'tipo', 'tipo_medidor']
    readonly_fields = ['nombre', 'tipo', 'tipo_medidor']
    show_change_link = True
    ordering = ['nombre']
    list_per_page = 10
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('tipo_medidor')
#Admin Class para el modelo Medidor
@admin.register(Medidor)
class MedidorAdmin(admin.ModelAdmin):
    list_display = ['id','nombre', 'tipo', 'tipo_medidor', 'medidor_padre']
    search_fields = ['nombre']
    list_filter = ['tipo', 'tipo_medidor']
    ordering = ['nombre']
    list_per_page = 10
    #agrega el inline de medidores hijos


    inlines = [MedidorInline]
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('tipo_medidor', 'medidor_padre')
    def medidores_count(self, obj):
        return obj.medidores.count()

# Registrar los modelos fuera de la clase ConsumoAdmin
admin.site.register(InterfaceConsumo)

admin.site.register(PuntoMedicion)
admin.site.register(Equipo)
admin.site.register(CaracteristicaMedicion)
admin.site.register(CategoriaPuntoMedicion)
admin.site.register(DocumentoMedicion)
admin.site.register(RangoMedicion)

@admin.register(VistaConsumoDiferencia)
class VistaConsumoDiferenciaAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'medidor_id', 'consumo', 'consumo_anterior', 'diferencia_consumo']
    list_filter = ['fecha', 'medidor_id']
    search_fields = ['medidor_id']
    readonly_fields = [f.name for f in VistaConsumoDiferencia._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False