from django import forms
from .models import Auditoria
from activos.models import Ubicacion, Categoria
from django.contrib.admin.widgets import FilteredSelectMultiple

class AuditoriaStep1Form(forms.ModelForm):
    class Meta:
        model = Auditoria
        fields = ['nombre', 'fecha_fin']
        widgets = {
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}),
        }

class AuditoriaStep2Form(forms.Form):
    ubicaciones = forms.ModelMultipleChoiceField(
        queryset=Ubicacion.objects.all(),
        widget=FilteredSelectMultiple("Ubicaciones", is_stacked=False),
        required=False
    )
    categorias = forms.ModelMultipleChoiceField(
        queryset=Categoria.objects.all(),
        widget=FilteredSelectMultiple("Categorías", is_stacked=False),
        required=False
    )
    
    class Media:
        css = {
            'all': ('/static/admin/css/widgets.css',),
        }
        js = ('/admin/jsi18n/',)
