from django.db import models
from django.utils import timezone
from pgvector.django import VectorField


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
    
    # Búsqueda vectorial semántica (embedding resumen)
    embedding = VectorField(dimensions=384, null=True, blank=True)
    
    # Vinculación con Rutinas de Mantenimiento
    rutinas = models.ManyToManyField(
        'mantenimiento.Rutina',
        blank=True,
        related_name='kpis',
        help_text="Rutinas de mantenimiento vinculadas a este KPI"
    )
    frecuencia_supervision = models.ForeignKey(
        'mantenimiento.Frecuencia',
        on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Frecuencia de Supervisión",
        help_text="Frecuencia con la que se supervisa este KPI"
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


class KPIFragmento(models.Model):
    """Fragmento vectorizado de un KPI para búsqueda semántica RAG."""
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name='fragmentos')
    contenido = models.TextField(help_text="Texto compuesto del KPI para búsqueda semántica")
    embedding = VectorField(dimensions=384, null=True, blank=True)
    orden = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Fragmento de KPI"
        verbose_name_plural = "Fragmentos de KPIs"
        ordering = ['kpi', 'orden']
        indexes = [
            models.Index(fields=['kpi']),
        ]

    def __str__(self):
        return f"Fragmento {self.orden} de KPI {self.kpi_id}"


class KPIArchivo(models.Model):
    """Archivo adjunto directamente a un KPI (carpeta de documentos)."""
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name='archivos')
    archivo = models.FileField(upload_to='kpi_documentos/')
    nombre = models.CharField(max_length=255, blank=True)
    descripcion = models.TextField(blank=True, default='')
    subido_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Documento de KPI"
        verbose_name_plural = "Documentos de KPI"
        ordering = ['-creado_en']

    def __str__(self):
        return self.nombre or (self.archivo.name if self.archivo else 'Documento')

    def save(self, *args, **kwargs):
        if not self.nombre and self.archivo:
            import os
            self.nombre = os.path.basename(self.archivo.name)
        super().save(*args, **kwargs)


# --- Signal: Auto-vectorización de KPIs al guardar ---
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=KPI)
def auto_vectorize_kpi(sender, instance, **kwargs):
    """Dispara la vectorización asíncrona del KPI cada vez que se guarda."""
    try:
        from .tasks import generate_kpi_embedding
        generate_kpi_embedding.delay(instance.id)
    except Exception:
        pass  # Silenciar si Celery/Redis no está disponible


# --- Importar modelos de riesgos para que Django los descubra ---
from .models_riesgos import (  # noqa: E402, F401
    Riesgo,
    EvaluacionRiesgo,
    ConfiguracionRiesgoServicio,
    PlanTratamiento,
    AccionTratamiento,
    RevisionRiesgo,
    RiesgoHistorial,
)
