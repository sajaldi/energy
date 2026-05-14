from django import forms
from django.contrib import admin
from .models import Activo

class ActivoAdminForm(forms.ModelForm):
    class Meta:
        model = Activo
        fields = '__all__'
        widgets = {
            'ubicacion': admin.widgets.AutocompleteSelect(Activo._meta.get_field('ubicacion').remote_field, admin.site),
            'responsable': admin.widgets.AutocompleteSelect(Activo._meta.get_field('responsable').remote_field, admin.site),
            'modelo': admin.widgets.AutocompleteSelect(Activo._meta.get_field('modelo').remote_field, admin.site),
            'familia': admin.widgets.AutocompleteSelect(Activo._meta.get_field('familia').remote_field, admin.site),
            'padre': admin.widgets.AutocompleteSelect(Activo._meta.get_field('padre').remote_field, admin.site),
            'plano': admin.widgets.AutocompleteSelect(Activo._meta.get_field('plano').remote_field, admin.site),
        }

    def clean(self):
        cleaned_data = super().clean()
        # Si hay errores (validación de campos fallida), recopilarlos para el mensaje superior
        if self.errors:
            missing_fields = []
            for field_name, error_list in self.errors.items():
                if field_name != '__all__':
                    # Obtener el label del campo
                    field_obj = self.fields.get(field_name)
                    label = field_obj.label if field_obj else field_name
                    # Verificar si el error parece ser de "requerido"
                    # Aunque para el usuario, cualquier error impeditivo cuenta, 
                    # el requerimiento es "qué campo obligatorio no se llenó".
                    # Asumimos que si está en errors y es required, es eso.
                    if field_obj and field_obj.required:
                        missing_fields.append(label)
                    else:
                        # Si no es required pero tiene error (ej. validación regex), agregarlo también
                        missing_fields.append(f"{label} ({error_list[0]})")
            
            if missing_fields:
                from django.core.exceptions import ValidationError
                # Usamos un mensaje HTML-safe o texto plano
                msg = f"⛔ NO SE PUDO GUARDAR. Faltan o tienen error los siguientes campos: {', '.join(missing_fields)}"
                # USAMOS add_error con None para agregar al top sin borrar los errores de campo
                self.add_error(None, msg)
        
        return cleaned_data
