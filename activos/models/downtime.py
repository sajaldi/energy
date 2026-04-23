from django.db import models
from django.utils import timezone

class DowntimeActivo(models.Model):
    activo = models.ForeignKey('activos.Activo', on_delete=models.CASCADE, related_name='historial_paradas')
    orden_trabajo = models.ForeignKey('mantenimiento.OrdenTrabajo', on_delete=models.CASCADE, related_name='downtimes', null=True, blank=True)
    aviso = models.ForeignKey('mantenimiento.Aviso', on_delete=models.CASCADE, related_name='downtimes', null=True, blank=True)

    
    inicio = models.DateTimeField(default=timezone.now, db_index=True)
    fin = models.DateTimeField(null=True, blank=True, db_index=True)
    
    duracion_horas = models.FloatField(default=0, help_text="Duración calculada en horas")
    
    motivo = models.CharField(max_length=255, blank=True, null=True)
    hallazgos = models.TextField(blank=True, null=True)
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Parada: {self.activo.nombre} ({self.inicio.date()})"

    def save(self, *args, **kwargs):
        if self.fin and self.inicio:
            delta = self.fin - self.inicio
            self.duracion_horas = delta.total_seconds() / 3600.0
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Historial de Parada"
        verbose_name_plural = "Historial de Paradas"
        ordering = ['-inicio']
        app_label = 'activos'
