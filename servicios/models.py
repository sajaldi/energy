from django.db import models
from django.utils import timezone


class Servicio(models.Model):
    """Modelo para gestionar servicios"""
    nombre = models.CharField(max_length=200, unique=True)
    descripcion = models.TextField(blank=True)
    codigo = models.CharField(max_length=50, unique=True, blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class KPI(models.Model):
    """Modelo para Key Performance Indicators (Indicadores Clave de Desempeño)"""
    TIPO_CHOICES = [
        ('porcentaje', 'Porcentaje'),
        ('numero', 'Número'),
        ('tiempo', 'Tiempo'),
        ('costo', 'Costo'),
    ]
    
    servicio = models.ForeignKey(
        Servicio, 
        on_delete=models.CASCADE, 
        related_name='kpis'
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='numero')
    meta = models.DecimalField(max_digits=10, decimal_places=2, help_text="Meta u objetivo del KPI")
    valor_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unidad_medida = models.CharField(max_length=50, blank=True, help_text="Ej: %, horas, USD, etc.")
    
    # Fechas
    fecha_medicion = models.DateField(default=timezone.now)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "KPI"
        verbose_name_plural = "KPIs"
        ordering = ['-fecha_medicion', 'servicio']
        
    def __str__(self):
        return f"{self.servicio.nombre} - {self.nombre}"
    
    @property
    def porcentaje_cumplimiento(self):
        """Calcula el porcentaje de cumplimiento respecto a la meta"""
        if self.meta > 0:
            return (self.valor_actual / self.meta) * 100
        return 0
