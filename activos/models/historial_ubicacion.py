from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class HistorialUbicacionActivo(models.Model):
    """
    Registra el historial de cambios de ubicación de un activo.
    Cada vez que se cambia la ubicación de un activo, se crea un registro aquí.
    """
    activo = models.ForeignKey(
        'activos.Activo',
        on_delete=models.CASCADE,
        related_name='historial_ubicaciones',
        help_text="Activo al que pertenece este historial"
    )
    
    ubicacion_anterior = models.ForeignKey(
        'activos.Ubicacion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_como_anterior',
        help_text="Ubicación anterior del activo"
    )
    
    ubicacion_nueva = models.ForeignKey(
        'activos.Ubicacion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_como_nueva',
        help_text="Nueva ubicación del activo"
    )
    
    fecha_cambio = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Fecha y hora del cambio de ubicación"
    )
    
    comentarios = models.TextField(
        blank=True,
        null=True,
        help_text="Comentarios o razón del cambio de ubicación"
    )
    
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cambios_ubicacion_realizados',
        help_text="Usuario que realizó el cambio"
    )
    
    # Campos adicionales útiles
    plano_anterior = models.ForeignKey(
        'activos.Plano',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_plano_anterior',
        help_text="Plano anterior (opcional)"
    )
    
    plano_nuevo = models.ForeignKey(
        'activos.Plano',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_plano_nuevo',
        help_text="Plano nuevo (opcional)"
    )
    
    creado_en = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        ubicacion_ant = self.ubicacion_anterior.nombre if self.ubicacion_anterior else "Sin ubicación"
        ubicacion_nva = self.ubicacion_nueva.nombre if self.ubicacion_nueva else "Sin ubicación"
        return f"{self.activo.codigo_interno} - {ubicacion_ant} → {ubicacion_nva} ({self.fecha_cambio.strftime('%d/%m/%Y')})"
    
    class Meta:
        verbose_name = "Historial de Ubicación"
        verbose_name_plural = "Historial de Ubicaciones"
        ordering = ['-fecha_cambio']
        app_label = 'activos'
        indexes = [
            models.Index(fields=['activo', '-fecha_cambio']),
            models.Index(fields=['fecha_cambio']),
        ]
