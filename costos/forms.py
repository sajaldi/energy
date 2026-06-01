from django import forms
from .models import AnalisisCostoUnitario, DetalleCostoUnitario, FactorCosto


class AnalisisCostoUnitarioForm(forms.ModelForm):
    class Meta:
        model = AnalisisCostoUnitario
        fields = ['nombre', 'descripcion', 'unidad', 'proyecto', 'estado']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Nombre del concepto'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Descripción del análisis de costo unitario'
            }),
            'unidad': forms.Select(attrs={'class': 'form-control select2-material'}),
            'proyecto': forms.Select(attrs={'class': 'form-control select2-material'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
        }


class AnalisisCostoUnitarioCreateForm(AnalisisCostoUnitarioForm):
    class Meta(AnalisisCostoUnitarioForm.Meta):
        exclude = ['estado']


class DetalleCostoUnitarioForm(forms.ModelForm):
    class Meta:
        model = DetalleCostoUnitario
        fields = [
            'tipo_recurso', 'material', 'descripcion', 'unidad',
            'cantidad', 'precio_unitario', 'factor_rendimiento',
        ]
        widgets = {
            'tipo_recurso': forms.Select(attrs={'class': 'form-control'}),
            'material': forms.Select(attrs={
                'class': 'form-control select2-material',
            }),
            'descripcion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Descripción (si no aplica catálogo)'
            }),
            'unidad': forms.Select(attrs={'class': 'form-control select2-material'}),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.0001', 'min': '0.0001'
            }),
            'precio_unitario': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0'
            }),
            'factor_rendimiento': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.0001', 'min': '0.0001'
            }),
        }


class FactorCostoForm(forms.ModelForm):
    class Meta:
        model = FactorCosto
        fields = ['nombre', 'tipo', 'valor']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ej: Herramientas menores, Seguridad, etc.'
            }),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0'
            }),
        }
