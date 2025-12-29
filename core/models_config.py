from django.db import models
from colorfield.fields import ColorField

class ConfiguracionUI(models.Model):
    """
    Singleton model for storing global UI color settings.
    Includes colors for the Maintenance Matrix.
    """
    # General Theme
    titulo_proyecto = models.CharField(max_length=100, default="Energía", help_text="Título en la barra superior")
    color_primario = ColorField(default='#007bff', verbose_name="Color Primario (Botones, Headers)")
    color_secundario = ColorField(default='#6c757d', verbose_name="Color Secundario")
    
    # Matriz de Mantenimiento / Calendario
    matriz_header_bg = ColorField(default='#f8f9fa', verbose_name="Fondo Encabezado Matriz")
    matriz_header_text = ColorField(default='#333333', verbose_name="Texto Encabezado Matriz")
    matriz_border_color = ColorField(default='#dee2e6', verbose_name="Color de Bordes Matriz")
    
    # Estados de Celda (Hover, Active)
    matriz_hover_row = ColorField(default='rgba(0,0,0,0.05)', verbose_name="Hover Fila")
    matriz_hover_cell = ColorField(default='rgba(0,0,0,0.1)', verbose_name="Hover Celda")
    
    # Ordenes de Trabajo (Colores por tipo)
    orden_preventiva_bg = ColorField(default='#28a745', verbose_name="Fondo OT Preventiva")
    orden_correctiva_bg = ColorField(default='#dc3545', verbose_name="Fondo OT Correctiva")
    orden_texto = ColorField(default='#ffffff', verbose_name="Texto OT")

    def __str__(self):
        return "Configuración Visual del Sistema"

    def save(self, *args, **kwargs):
        # Singleton logic: ensure ID is always 1
        self.pk = 1
        super(ConfiguracionUI, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Prevent deletion
        pass

    class Meta:
        verbose_name = "Configuración Visual"
        verbose_name_plural = "Configuración Visual"
