from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import Servicio, KPI

class ServicioResource(resources.ModelResource):
    class Meta:
        model = Servicio
        fields = ('id', 'nombre', 'descripcion', 'codigo', 'activo', 'fecha_creacion', 'fecha_actualizacion')
        export_order = fields
        skip_unchanged = True
        report_skipped = True

class KPIResource(resources.ModelResource):
    servicio = fields.Field(
        column_name='servicio',
        attribute='servicio',
        widget=ForeignKeyWidget(Servicio, field='nombre')
    )

    class Meta:
        model = KPI
        fields = ('id', 'servicio', 'nombre', 'descripcion', 'forma_de_cumplimiento', 'metodo_de_supervision', 'categoria', 'estado', 'fecha_medicion', 'fecha_creacion', 'fecha_actualizacion')
        export_order = fields
        skip_unchanged = True
        report_skipped = True
