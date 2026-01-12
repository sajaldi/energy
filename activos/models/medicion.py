from django.db import models
from django.contrib.auth.models import User
from .activo import Activo

class PuntoMedicion(models.Model):
    """
    Representa un punto donde se pueden tomar lecturas para un activo (ej: Horímetro, Termómetro).
    """
    activo = models.ForeignKey(Activo, on_delete=models.CASCADE, related_name='puntos_medicion')
    nombre = models.CharField(max_length=100, help_text="Ej: Horímetro Motor, Presión Aceite")
    codigo = models.CharField(max_length=50, blank=True, null=True, help_text="Código corto opcional")
    
    unidad = models.CharField(max_length=20, help_text="Ej: Hrs, Bar, °C, PSI")
    es_acumulativo = models.BooleanField(default=False, help_text="Si se marca, el valor se suma al anterior (ej: horímetro)")
    
    valor_objetivo = models.FloatField(blank=True, null=True, help_text="Valor nominal o límite de operación")
    tolerancia = models.FloatField(blank=True, null=True, help_text="Rango de desviación permitido")
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    @property
    def ultima_lectura(self):
        return self.lecturas.first()

    @property
    def valor_actual(self):
        last = self.ultima_lectura
        return last.valor if last else None

    def __str__(self):
        return f"{self.activo.codigo_interno} - {self.nombre} ({self.unidad})"

    class Meta:
        verbose_name = "Punto de Medición"
        verbose_name_plural = "Puntos de Medición"
        app_label = 'activos'

class DocumentoMedicion(models.Model):
    """
    Representa una lectura individual tomada en un punto de medición.
    """
    punto = models.ForeignKey(PuntoMedicion, on_delete=models.CASCADE, related_name='lecturas')
    activo = models.ForeignKey(Activo, on_delete=models.CASCADE, related_name='lecturas_totales', null=True, blank=True)
    valor = models.FloatField()
    fecha_lectura = models.DateTimeField(default=None, null=True, blank=True)
    
    tecnico = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='lecturas_registradas')
    orden_trabajo = models.ForeignKey('mantenimiento.OrdenTrabajo', on_delete=models.SET_NULL, null=True, blank=True, related_name='documentos_medicion')
    
    observaciones = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if not self.fecha_lectura:
            self.fecha_lectura = timezone.now()
        if not self.activo and self.punto:
            self.activo = self.punto.activo
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.punto} - {self.valor} @ {self.fecha_lectura.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        verbose_name = "Documento de Medición"
        verbose_name_plural = "Documentos de Medición"
        ordering = ['-fecha_lectura']
        app_label = 'activos'
