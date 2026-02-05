from import_export import resources, fields, widgets
from .models import Requisicion
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

class RequisicionResource(resources.ModelResource):
    costo = fields.Field(
        column_name='costo', 
        attribute='cr8ca_totalenarticulos',
        widget=CleanDecimalWidget()
    )
    
    cr8ca_totalenarticulos = fields.Field(
        column_name='cr8ca_totalenarticulos',
        attribute='cr8ca_totalenarticulos',
        widget=CleanDecimalWidget()
    )
    
    class Meta:
        model = Requisicion
        import_id_fields = ('cr8ca_requisicion',)
        fields = (
            'cr8ca_requisicionid', 'cr8ca_requisicion', 'cr8ca_asunto', 'cr8ca_motivo', 
            'cr8ca_comentarios', 'cr8ca_totalenarticulos', 'costo', 'fecha', 'cr8ca_prioridad', 
            'cr8ca_tipodedocumento', 'cr8ca_estatusorden', 'cr8ca_id_oc', 'cr8ca_accion',
            '_cr8ca_presupuesto_value', '_cr8ca_proyecto_value', '_cr8ca_area_value',
            '_cr8ca_categoria_value', '_cr8ca_departamento_value', '_cr8ca_proveedorasignado_value',
            '_cr8ca_solicita_value', '_cr8ca_autoriza_value', '_cr8ca_reviso_value',
            'createdon', 'modifiedon'
        )
        export_order = fields
