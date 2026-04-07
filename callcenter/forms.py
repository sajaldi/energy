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
    # Campo virtual para entrada de texto de predecesores (ej: "1, 2")
    predecesores_texto = forms.CharField(
        required=False, 
        label="Predecesores (N°)", 
        widget=forms.TextInput(attrs={'class': 'ui-input', 'placeholder': 'Ej: 1, 2'})
    )

    class Meta:
        model = CronogramaItemPredefinido
        fields = ['numero', 'descripcion', 'duracion_dias']
        widgets = {
            'numero': forms.NumberInput(attrs={'class': 'ui-input-num', 'min': '1'}),
            'descripcion': forms.TextInput(attrs={'class': 'ui-input', 'placeholder': 'Descripción de tarea'}),
            'duracion_dias': forms.NumberInput(attrs={'class': 'ui-input-num', 'min': '1'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Obtener números de tareas predecesoras
            nums = self.instance.predecesores.values_list('numero', flat=True)
            if nums:
                self.initial['predecesores_texto'] = ", ".join(map(str, nums))

CronogramaItemFormSet = inlineformset_factory(
    CronogramaPredefinido,
    CronogramaItemPredefinido,
    form=CronogramaItemForm,
    extra=1,
    can_delete=True
)
