from django.db import models

class CaracteristicaCategoria(models.Model):
    TIPO_DATO_CHOICES = [
        ('TEXTO', 'Texto'),
        ('NUMERO', 'Número'),
        ('BOOLEANO', 'Sí/No (Booleano)'),
        ('OPCIONES', 'Lista de Opciones'),
    ]

    categoria = models.ForeignKey('activos.Categoria', on_delete=models.CASCADE, related_name='caracteristicas')
    nombre = models.CharField(max_length=100, help_text="Ej: Capacidad, Voltaje, Color")
    tipo_dato = models.CharField(max_length=20, choices=TIPO_DATO_CHOICES, default='TEXTO')
    unidad_medida = models.ForeignKey('core.UnidadMedida', on_delete=models.SET_NULL, null=True, blank=True)
    opciones = models.CharField(max_length=255, blank=True, null=True, help_text="Opciones separadas por coma si eligió 'Lista de Opciones'. Ej: Rojo,Verde,Azul")
    requerido = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.nombre} ({self.categoria.nombre})"

    class Meta:
        verbose_name = "Característica de Categoría"
        verbose_name_plural = "Características de Categoría"
        app_label = 'activos'


class ValorCaracteristicaModelo(models.Model):
    modelo = models.ForeignKey('activos.Modelo', on_delete=models.CASCADE, related_name='valores_caracteristicas')
    caracteristica = models.ForeignKey(CaracteristicaCategoria, on_delete=models.CASCADE)
    valor = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.modelo.nombre} - {self.caracteristica.nombre}: {self.valor}"

    class Meta:
        verbose_name = "Valor de Característica"
        verbose_name_plural = "Valores de Características"
        app_label = 'activos'
        unique_together = ('modelo', 'caracteristica')
