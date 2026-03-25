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
        ('MAYOR', 'Mayor'),
        ('MEDIA', 'Media'),
        ('MENOR', 'Menor'),
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
    comentarios = models.TextField(blank=True, default='', verbose_name="Comentarios adicionales")
    
    # Fechas
    fecha_medicion = models.DateField(default=timezone.now)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    # Vinculación con Rutinas de Mantenimiento
    rutinas = models.ManyToManyField(
        'mantenimiento.Rutina',
        blank=True,
        related_name='kpis',
        help_text="Rutinas de mantenimiento vinculadas a este KPI"
    )
    
    class Meta:
        verbose_name = "KPI"
        verbose_name_plural = "KPIs"
        ordering = ['-fecha_medicion', 'servicio']
        
    def __str__(self):
        return f"{self.servicio.nombre} - {self.categoria}"


class ChecklistItem(models.Model):
    """Elemento de checklist asociado a un KPI."""
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name='checklist_items')
    descripcion = models.CharField(max_length=255)
    completado = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']
        verbose_name = 'Elemento de Checklist'
        verbose_name_plural = 'Elementos de Checklist'

    def __str__(self):
        return f"{self.kpi.nombre} - {self.descripcion}"


class Auditoria(models.Model):
    """Modelo para representar una auditoría de KPIs."""
    nombre = models.CharField(max_length=200, help_text="Nombre de la auditoría (Ej: Auditoría Trimestral Q1 2026)")
    fecha = models.DateField(default=timezone.now)
    descripcion = models.TextField(blank=True, default='')
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Auditoría"
        verbose_name_plural = "Auditorías"
        ordering = ['-fecha']
        
    def __str__(self):
        return f"{self.nombre} ({self.fecha})"


class AuditoriaResultado(models.Model):
    """Resultado del desempeño de un KPI en una auditoría específica."""
    auditoria = models.ForeignKey(Auditoria, on_delete=models.CASCADE, related_name='resultados')
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name='resultados_auditoria')
    
    cumple = models.BooleanField(default=True, verbose_name="¿Cumple?")
    plan_de_accion = models.TextField(blank=True, default='', verbose_name="Plan de Acción")
    observaciones = models.TextField(blank=True, default='')
    
    class Meta:
        verbose_name = "Resultado de Auditoría"
        verbose_name_plural = "Resultados de Auditoría"
        unique_together = ('auditoria', 'kpi')
        
    def __str__(self):
        status = "Cumple" if self.cumple else "No Cumple"
        return f"{self.kpi.nombre} - {self.auditoria.nombre} ({status})"
