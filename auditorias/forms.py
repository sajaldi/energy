from django import forms
from .models import Auditoria
from activos.models import Ubicacion, Categoria
from django.contrib.admin.widgets import FilteredSelectMultiple

class AuditoriaStep1Form(forms.ModelForm):
    nombre = forms.CharField(required=False, label="Nombre de la Auditoría", help_text="Déjalo en blanco para generar uno automáticamente según la ubicación.")
    
    class Meta:
        model = Auditoria
        fields = ['nombre', 'tipo', 'fecha_fin']
        widgets = {
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}),
        }

class AuditoriaStep2Form(forms.Form):
    ubicaciones = forms.ModelMultipleChoiceField(
        queryset=Ubicacion.objects.all(),
        required=False
    )
    categorias = forms.ModelMultipleChoiceField(
        queryset=Categoria.objects.all(),
        required=False
    )
