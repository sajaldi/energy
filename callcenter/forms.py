from django import forms
from django.forms import inlineformset_factory
from .models import CronogramaPredefinido, CronogramaItemPredefinido

class CronogramaPredefinidoForm(forms.ModelForm):
    class Meta:
        model = CronogramaPredefinido
        fields = ['nombre', 'departamento']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'ui-input', 'placeholder': 'Ej: Mantenimiento Preventivo A'}),
            'departamento': forms.Select(attrs={'class': 'ui-select'}),
        }

class CronogramaItemForm(forms.ModelForm):
    class Meta:
        model = CronogramaItemPredefinido
        fields = ['numero', 'descripcion', 'duracion_dias', 'predecesores']
        widgets = {
            'numero': forms.NumberInput(attrs={'class': 'ui-input-num', 'min': '1'}),
            'descripcion': forms.TextInput(attrs={'class': 'ui-input', 'placeholder': 'Descripción de tarea'}),
            'duracion_dias': forms.NumberInput(attrs={'class': 'ui-input-num', 'min': '1'}),
            'predecesores': forms.SelectMultiple(attrs={'class': 'ui-select-multiple'}),
        }

CronogramaItemFormSet = inlineformset_factory(
    CronogramaPredefinido,
    CronogramaItemPredefinido,
    form=CronogramaItemForm,
    extra=1,
    can_delete=True
)
