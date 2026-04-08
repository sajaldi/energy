from import_export import resources, fields, widgets
from import_export.widgets import ForeignKeyWidget
from .models import Requisicion, ItemSolicitudPago, SolicitudPago
from mantenimiento.models import Empresa
from django.contrib.auth.models import User
import decimal

class CleanDecimalWidget(widgets.DecimalWidget):
    """
    Limpia símbolos de moneda, comas y espacios antes de convertir a Decimal.
    """
    def clean(self, value, row=None, *args, **kwargs):
        if value is None:
            return None
            
        # Si ya es un número, convertir a string de forma segura
        if isinstance(value, (int, float, decimal.Decimal)):
            val_str = str(value)
        else:
            val_str = str(value).strip()

        if not val_str or val_str.lower() in ['none', 'nan', 'null', '']:
            return None
            
        # Limpieza profunda:
        # 1. Quitar símbolos de moneda y espacios
        # 2. Quitar comas (separadores de miles usuales)
        val_str = val_str.replace('$', '').replace('L.', '').replace('L', '').replace(' ', '').replace(',', '')
        
        # 3. Solo permitir caracteres numéricos, punto y signo menos
        # (Esto protege contra basura al final del string)
        import re
        val_str = re.sub(r'[^0-9.-]', '', val_str)
        
        if not val_str or val_str == '.' or val_str == '-':
            return None
            
        try:
            return decimal.Decimal(val_str)
        except (decimal.InvalidOperation, ValueError, TypeError):
            # No devolvemos None aquí para que import-export pueda reportar el error real si no es opcional
            # o si queremos que el usuario sepa que el dato está mal.
            # Pero para evitar el 'ConversionSyntax' genérico, lanzamos una excepción limpia.
            raise ValueError(f"'{value}' no es un número válido.")

class CachedForeignKeyWidget(ForeignKeyWidget):
    """
    Widget que cachea los resultados de foreign key para evitar miles de queries idénticas.
    """
    def __init__(self, model, field='pk', *args, **kwargs):
        super().__init__(model, field, *args, **kwargs)
        self._cache = {}

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        
        # Cache key: (value) -> instance
        if value in self._cache:
            return self._cache[value]
            
        instance = super().clean(value, row, *args, **kwargs)
        if instance:
            self._cache[value] = instance
        return instance

class RequisicionResource(resources.ModelResource):
    cr8ca_totalenarticulos = fields.Field(
        column_name='cr8ca_totalenarticulos',
        attribute='cr8ca_totalenarticulos',
        widget=CleanDecimalWidget()
    )

    proveedor = fields.Field(
        column_name='proveedor',
        attribute='proveedor',
        widget=CachedForeignKeyWidget(Empresa, field='nombre')
    )
    
    usuario_solicitante = fields.Field(
        column_name='usuario_solicitante',
        attribute='usuario_solicitante',
        widget=CachedForeignKeyWidget(User, field='username')
    )
    
    def before_import_row(self, row, **kwargs):
        """
        Mapea manualmente columnas alias (ej: costo -> cr8ca_totalenarticulos)
        y elimina campos vacíos para evitar sobrescribir con NULL.
        """
        # Si viene 'costo' y no 'cr8ca_totalenarticulos', usamos costo
        if 'costo' in row and not row.get('cr8ca_totalenarticulos'):
            row['cr8ca_totalenarticulos'] = row['costo']
        
        # Lógica de actualización parcial:
        # Si un campo viene vacío en el Excel, lo quitamos del 'row'
        # para que django-import-export NO intente actualizar ese campo en la instancia.
        keys_to_remove = []
        for k, v in row.items():
            # Consideramos vacío: None, string vacío, 'None', 'nan', 'NULL'
            if v is None:
                keys_to_remove.append(k)
            elif isinstance(v, str) and (not v.strip() or v.strip().lower() in ['none', 'nan', 'null']):
                keys_to_remove.append(k)
        
        for k in keys_to_remove:
            if k in row:
                del row[k]

    class Meta:
        model = Requisicion
        import_id_fields = ('cr8ca_requisicion',)
        fields = (
            'cr8ca_requisicion', 'cr8ca_asunto', 'cr8ca_motivo', 
            'cr8ca_comentarios', 'proveedor', 'cr8ca_totalenarticulos', 'fecha', 'cr8ca_prioridad', 
            'cr8ca_id_oc', 'usuario_solicitante',
            'createdon', 'modifiedon'
        )
        export_order = fields
        use_bulk = True
        batch_size = 1000
        skip_diff = True

class ItemSolicitudPagoResource(resources.ModelResource):
    solicitud = fields.Field(
        column_name='solicitud_id',
        attribute='solicitud',
        widget=CachedForeignKeyWidget(SolicitudPago, field='pk')
    )
    requisicion = fields.Field(
        column_name='requisicion_codigo',
        attribute='requisicion',
        widget=CachedForeignKeyWidget(Requisicion, field='cr8ca_requisicion')
    )
    monto_solicitado = fields.Field(
        column_name='monto_solicitado',
        attribute='monto_solicitado',
        widget=CleanDecimalWidget()
    )

    def before_import_row(self, row, **kwargs):
        # Alias comunes
        if 'monto' in row and not row.get('monto_solicitado'):
            row['monto_solicitado'] = row['monto']
        if 'codigo_requisicion' in row and not row.get('requisicion_codigo'):
            row['requisicion_codigo'] = row['codigo_requisicion']
        
        # Si se pasó un solicitud_id por kwargs (desde la vista), forzarlo en el row
        if 'solicitud_id' in kwargs:
            row['solicitud_id'] = kwargs['solicitud_id']

    class Meta:
        model = ItemSolicitudPago
        import_id_fields = ('solicitud', 'requisicion')
        fields = ('solicitud', 'requisicion', 'monto_solicitado', 'condicion_pago', 'descripcion', 'estatus')
        use_bulk = True
        skip_diff = True
