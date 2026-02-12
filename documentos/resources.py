from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from django.contrib.auth.models import User
from .models import ComentarioDocumento, Documento, Revision

class ComentarioDocumentoResource(resources.ModelResource):
    documento_codigo = fields.Field(
        column_name='documento_codigo',
        attribute='documento',
        widget=ForeignKeyWidget(Documento, field='codigo')
    )
    usuario_username = fields.Field(
        column_name='usuario',
        attribute='usuario',
        widget=ForeignKeyWidget(User, field='username')
    )
    
    class Meta:
        model = ComentarioDocumento
        fields = ('id', 'documento_codigo', 'usuario_username', 'texto', 'pagina', 'posicion_x', 'posicion_y', 'resuelto')
        export_order = ('id', 'documento_codigo', 'usuario_username', 'texto', 'pagina', 'posicion_x', 'posicion_y', 'resuelto')
        skip_unchanged = True
        report_skipped = True
        import_id_fields = ('id',)

    def before_import_row(self, row, **kwargs):
        """Limpieza de datos"""
        for key in list(row.keys()):
            val = row.get(key)
            if val is not None:
                val_str = str(val).strip()
                if val_str.lower() in ['none', 'nan', 'null', '']:
                    row[key] = None
                elif isinstance(val, str):
                    row[key] = val_str

        # Si no tiene pagina, asumir 1
        if not row.get('pagina'):
            row['pagina'] = 1
