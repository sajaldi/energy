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
    CATEGORIA_CHOICES = [
        ('MEJORA', 'Mejora'),
        ('MAYOR', 'Mayor'),
    ]
    ESTADO_CHOICES = [
        ('CUMPLIMIENTO', 'En Cumplimiento'),
        ('PARCIAL', 'Cumplimiento Parcial'),
        ('INCUMPLIMIENTO', 'Incumplimiento'),
    ]
    
    servicio = models.ForeignKey(
        Servicio, 
        on_delete=models.CASCADE, 
        related_name='kpis'
    )
    nombre = models.CharField(max_length=200, blank=True, default='')
    descripcion = models.TextField(blank=True, default='')
    forma_de_cumplimiento = models.TextField(blank=True, default='', help_text="Forma de cumplimiento (Texto)")
    metodo_de_supervision = models.TextField(blank=True, default='', help_text="Método de Supervisión (Texto)")
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='MAYOR')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='CUMPLIMIENTO')
    
    # Fechas
    fecha_medicion = models.DateField(default=timezone.now)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "KPI"
        verbose_name_plural = "KPIs"
        ordering = ['-fecha_medicion', 'servicio']
        
    def __str__(self):
        return f"{self.servicio.nombre} - {self.categoria}"
