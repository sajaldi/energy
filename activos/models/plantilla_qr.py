from django.db import models

class PlantillaEtiquetaQR(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Molde")
    ancho_cm = models.DecimalField(max_digits=5, decimal_places=2, default=5.0, verbose_name="Ancho (cm)")
    alto_cm = models.DecimalField(max_digits=5, decimal_places=2, default=5.0, verbose_name="Alto (cm)")
    
    # Defaults paramétricos
    prefijo_defecto = models.CharField(max_length=10, blank=True, null=True, default="", verbose_name="Prefijo Frecuente")
    padding_digitos = models.IntegerField(default=5, verbose_name="Dígitos de Padding")
    
    # Paramétricos de Previsualización (WYSIWYG config)
    header_text = models.CharField(max_length=100, blank=True, null=True, verbose_name="Texto Cabecera")
    footer_mode = models.CharField(max_length=50, default="secuencial", choices=[('secuencial', 'Secuencial Automático'), ('vacio', 'Vacío')], verbose_name="Modo de Pie")
    font_size = models.IntegerField(default=10, verbose_name="Tamaño Fuente (pt)")
    qr_scale = models.IntegerField(default=80, verbose_name="Escala QR (%)")
    border_thickness = models.IntegerField(default=1, verbose_name="Grosor Borde (px)")
    margin_top = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name="Margen Superior (cm)")

    # HTML compilado
    compiled_html = models.TextField(blank=True, null=True, verbose_name="HTML Compilado Interno")

    activo = models.BooleanField(default=True, verbose_name="Activo")
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plantilla QR"
        verbose_name_plural = "Plantillas QR"
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.nombre} ({self.ancho_cm}x{self.alto_cm} cm)"
