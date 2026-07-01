from django import forms
from .models import Curso, Seccion


class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ['titulo', 'descripcion', 'imagen', 'activo']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }


class SeccionForm(forms.ModelForm):
    class Meta:
        model = Seccion
        fields = ['orden', 'titulo', 'contenido_html', 'duracion_minutos', 'obligatorio']
        widgets = {
            'contenido_html': forms.Textarea(attrs={'rows': 8, 'class': 'html-editor'}),
            'orden': forms.NumberInput(attrs={'class': 'orden-input', 'size': 3}),
            'duracion_minutos': forms.NumberInput(attrs={'size': 4}),
        }


SeccionFormSet = forms.inlineformset_factory(
    Curso, Seccion,
    form=SeccionForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)
