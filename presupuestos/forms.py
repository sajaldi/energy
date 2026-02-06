from django import forms
from .models import Requisicion, ArticuloRequisicion, DocumentoRequisicion
from inventarios.models import Material

class RequisicionForm(forms.ModelForm):
    class Meta:
        model = Requisicion
        fields = [
            'cr8ca_requisicion', 'fecha', 'usuario_solicitante', 'usuario_en_nombre_de', 'cr8ca_asunto', 'cr8ca_prioridad', 
            'cr8ca_motivo', 'cr8ca_comentarios', 'cr8ca_id_oc', 'wizard_step', 'estado_requisicion', 'cr8ca_totalenarticulos'
        ]
        widgets = {
            'cr8ca_requisicion': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cr8ca_asunto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Asunto de la requisición'}),
            'cr8ca_prioridad': forms.Select(attrs={'class': 'form-control'}),
            'cr8ca_motivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'cr8ca_comentarios': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'usuario_solicitante': forms.Select(attrs={'class': 'form-control', 'disabled': 'disabled'}),
            'usuario_en_nombre_de': forms.Select(attrs={'class': 'form-control select2-material'}),
            'cr8ca_id_oc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID de Orden de Compra'}),
            'estado_requisicion': forms.Select(attrs={'class': 'form-control', 'disabled': 'disabled'}),
            'cr8ca_totalenarticulos': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
        }
        labels = {
            'cr8ca_totalenarticulos': 'Costo Aproximado'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'cr8ca_requisicion' in self.fields:
            self.fields['cr8ca_requisicion'].required = False
        if 'estado_requisicion' in self.fields:
            self.fields['estado_requisicion'].required = False

class ArticuloRequisicionForm(forms.ModelForm):
    class Meta:
        model = ArticuloRequisicion
        fields = ['material', 'cr8ca_articulo', 'cr8ca_cantidad', 'cr8ca_costoaproximado']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-control select2-material'}),
            'cr8ca_articulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descripción del artículo'}),
            'cr8ca_cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cr8ca_costoaproximado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make UUID field not required for new instances
        if 'cr8ca_itemderequisicionid' in self.fields:
            self.fields['cr8ca_itemderequisicionid'].required = False
            self.fields['cr8ca_itemderequisicionid'].widget = forms.HiddenInput()

ArticuloFormSet = forms.inlineformset_factory(
    Requisicion, ArticuloRequisicion,
    form=ArticuloRequisicionForm,
    extra=1,
    can_delete=True
)

class DocumentoRequisicionForm(forms.ModelForm):
    class Meta:
        model = DocumentoRequisicion
        fields = ['archivo', 'nombre']
        widgets = {
            'archivo': forms.FileInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del archivo'}),
        }

DocumentoFormSet = forms.inlineformset_factory(
    Requisicion, DocumentoRequisicion,
    form=DocumentoRequisicionForm,
    extra=1,
    can_delete=True
)
