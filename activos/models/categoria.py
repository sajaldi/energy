from django.db import models

class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    padre = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategorias')
    icono = models.CharField(max_length=50, default='location', help_text="Nombre del icono de Ionicons (ej: flash, water, construct, bulb)")
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        app_label = 'activos'
