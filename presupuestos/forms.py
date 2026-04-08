from django import forms
from .models import Requisicion, ArticuloRequisicion, DocumentoRequisicion
from inventarios.models import Material

class RequisicionForm(forms.ModelForm):
    class Meta:
        model = Requisicion
        fields = [
            'cr8ca_requisicion', 'fecha', 'fecha_aprobacion', 'partida', 'item_presupuesto', 'tipo_rutina', 'usuario_solicitante', 'usuario_en_nombre_de', 'cr8ca_asunto', 'cr8ca_prioridad', 
            'cr8ca_motivo', 'cr8ca_comentarios', 'cr8ca_id_oc', 'wizard_step', 'estado_requisicion', 'cr8ca_totalenarticulos',
            'proveedor', 'proveedores_sugeridos', 'proveedores_sugeridos_notas'
        ]
        widgets = {
            'cr8ca_requisicion': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'fecha': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'fecha_aprobacion': forms.DateTimeInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'partida': forms.Select(attrs={'class': 'form-control select2-material'}),
            'item_presupuesto': forms.Select(attrs={'class': 'form-control select2-material'}),
            'tipo_rutina': forms.Select(attrs={'class': 'form-control select2-material'}),
            'cr8ca_asunto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Asunto de la requisición'}),
            'cr8ca_prioridad': forms.Select(attrs={'class': 'form-control'}),
            'cr8ca_motivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Explica por qué se requiere la compra', 'title': 'Explica el por qué se requiere la compra'}),
            'cr8ca_comentarios': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'usuario_solicitante': forms.Select(attrs={'class': 'form-control', 'disabled': 'disabled'}),
            'usuario_en_nombre_de': forms.Select(attrs={'class': 'form-control select2-material'}),
            'cr8ca_id_oc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID de Orden de Compra'}),
            'estado_requisicion': forms.Select(attrs={'class': 'form-control', 'disabled': 'disabled'}),
            'cr8ca_totalenarticulos': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'proveedor': forms.Select(attrs={'class': 'form-control select2-material'}),
            'proveedores_sugeridos': forms.SelectMultiple(attrs={
                'class': 'form-control select2-material',
                'multiple': 'multiple'
            }),
            'proveedores_sugeridos_notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Detalle de qué artículos corresponden a cada proveedor...'}),
        }
        labels = {
            'cr8ca_totalenarticulos': 'Costo Aproximado'
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if 'cr8ca_requisicion' in self.fields:
            self.fields['cr8ca_requisicion'].required = False
        if 'estado_requisicion' in self.fields:
            self.fields['estado_requisicion'].required = False
        if 'usuario_solicitante' in self.fields:
            self.fields['usuario_solicitante'].required = False

        # Filtrar partidas e ítems por departamento del usuario
        if self.user and 'partida' in self.fields:
            from presupuestos.models import PartidaPresupuestaria, ItemPresupuesto
            user_depto_id = None
            if hasattr(self.user, 'perfil') and self.user.perfil.departamento_id:
                user_depto_id = self.user.perfil.departamento_id

            if user_depto_id:
                # Partidas que pertenecen al departamento del usuario O que no tienen departamentos (globales)
                from django.db.models import Q
                partidas_permitidas = PartidaPresupuestaria.objects.filter(
                    Q(departamentos__id=user_depto_id) | Q(departamentos__isnull=True)
                ).distinct()
                self.fields['partida'].queryset = partidas_permitidas

                # Filtrar también los ítems de presupuesto a solo los de partidas permitidas
                if 'item_presupuesto' in self.fields:
                    self.fields['item_presupuesto'].queryset = ItemPresupuesto.objects.filter(
                        partida__in=partidas_permitidas
                    )
            # Si el usuario no tiene departamento, ve todas (comportamiento por defecto)

class ArticuloRequisicionForm(forms.ModelForm):
    class Meta:
        model = ArticuloRequisicion
        fields = ['cr8ca_itemderequisicionid', 'proveedor', 'material', 'cr8ca_articulo', 'cr8ca_cantidad', 'cr8ca_costoaproximado']
        widgets = {
            'cr8ca_itemderequisicionid': forms.HiddenInput(),
            'proveedor': forms.Select(attrs={'class': 'form-control select2-material'}),
            'material': forms.Select(attrs={'class': 'form-control select2-material'}),
            'cr8ca_articulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descripción del artículo'}),
            'cr8ca_cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cr8ca_costoaproximado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # PK must be non-required for new rows in formsets
        if 'cr8ca_itemderequisicionid' in self.fields:
            self.fields['cr8ca_itemderequisicionid'].required = False
            self.fields['cr8ca_itemderequisicionid'].widget = forms.HiddenInput()
            
            # Si la instancia no ha sido guardada (no existe en DB),
            # limpiamos el valor inicial del UUID para evitar que el 'empty_form'
            # del formset use el mismo UUID para todas las filas nuevas.
            if self.instance._state.adding:
                self.initial['cr8ca_itemderequisicionid'] = ''
        
        if 'id' in self.fields:
            self.fields['id'].required = False
            self.fields['id'].widget = forms.HiddenInput()

ArticuloFormSet = forms.inlineformset_factory(
    Requisicion, ArticuloRequisicion,
    form=ArticuloRequisicionForm,
    extra=0,
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
