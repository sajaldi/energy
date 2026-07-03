from django import forms
from .models import Curso, Seccion


class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ['titulo', 'descripcion', 'imagen', 'padre', 'orden', 'activo']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'orden': forms.NumberInput(attrs={'size': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        qs = Curso.objects.all()
        if instance:
            qs = qs.exclude(pk=instance.pk)
        self.fields['padre'].queryset = qs
        self.fields['padre'].label = "Curso padre (pensum)"
        self.fields['padre'].empty_label = "— Curso independiente —"
        self.fields['orden'].label = "Orden dentro del pensum"
        self.fields['orden'].help_text = "Posición del curso dentro del pensum padre"


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
    extra=0,
    can_delete=True,
    min_num=0,
    validate_min=False,
)
