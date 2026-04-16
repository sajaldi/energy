from django.db import models
from django.contrib.auth.models import User
from core.storage import MinIOStorage
import uuid

minio_storage = MinIOStorage()

class ReporteGenerado(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('PROCESANDO', 'En Proceso'),
        ('COMPLETADO', 'Completado'),
        ('ERROR', 'Error'),
        ('CANCELADO', 'Cancelado'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reportes_generados')
    nombre = models.CharField(max_length=200, help_text="Nombre descriptivo del reporte")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    task_id = models.CharField(max_length=255, blank=True, null=True, help_text="ID de la tarea en Celery")
    
    archivo = models.FileField(upload_to='reportes_generados/', storage=minio_storage, blank=True, null=True)
    detalles_error = models.TextField(blank=True, null=True)
    
    creado_en = models.DateTimeField(auto_now_add=True)
    completado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Reporte Generado"
        verbose_name_plural = "Reportes Generados"
        ordering = ['-creado_en']
        app_label = 'activos'

    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"
