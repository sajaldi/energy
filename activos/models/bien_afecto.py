from django.db import models
from django.contrib.auth.models import User

class BienAfecto(models.Model):
    """
    Representa un código patrimonial permanente.
    Puede tener múltiples activos físicos a lo largo del tiempo.
    """
    codigo_interno = models.CharField(
        max_length=50, 
        unique=True,
        db_index=True,
        help_text="Código patrimonial permanente"
    )
    nombre = models.CharField(max_length=200, help_text="Descripción del bien afecto")
    
    ubicacion = models.ForeignKey(
        'Ubicacion', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='bienes_afectos',
        help_text="Ubicación actual del bien afecto"
    )
    
    familia = models.ForeignKey(
        'Familia', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='bienes_afectos',
        help_text="Clasificación por familia"
    )
    
    responsable = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='bienes_afectos_responsable',
        help_text="Persona responsable del bien afecto"
    )
    
    # Campos de auditoría
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    
    @property
    def activo_actual(self):
        """Retorna el activo físico actualmente asignado (sin fecha de baja)"""
        historial_activo = self.historial.filter(fecha_baja__isnull=True).first()
        return historial_activo.activo if historial_activo else None
    
    def __str__(self):
        return f"{self.codigo_interno} - {self.nombre}"
    
    class Meta:
        verbose_name = "Bien Afecto"
        verbose_name_plural = "Bienes Afectos"
        app_label = 'activos'
        ordering = ['codigo_interno']


class HistorialBienAfecto(models.Model):
    """
    Registro de altas y bajas de activos físicos en un bien afecto.
    Permite mantener trazabilidad completa de qué equipos han ocupado un código patrimonial.
    """
    MOTIVO_BAJA_CHOICES = [
        ('REEMPLAZO', 'Reemplazo por nuevo equipo'),
        ('OBSOLETO', 'Equipo obsoleto'),
        ('DAÑADO', 'Equipo dañado irreparable'),
        ('ROBO', 'Robo o extravío'),
        ('TRANSFERENCIA', 'Transferencia a otro bien afecto'),
        ('OTRO', 'Otro motivo'),
    ]
    
    bien_afecto = models.ForeignKey(
        BienAfecto, 
        on_delete=models.CASCADE,
        related_name='historial',
        help_text="Bien afecto al que pertenece este registro"
    )
    
    activo = models.ForeignKey(
        'Activo', 
        on_delete=models.CASCADE,
        related_name='historial_bien_afecto',
        help_text="Activo físico asignado"
    )
    
    # Datos de alta
    fecha_alta = models.DateTimeField(auto_now_add=True, help_text="Fecha de asignación del activo")
    usuario_alta = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,
        null=True,
        related_name='altas_bien_afecto',
        help_text="Usuario que dio de alta el activo"
    )
    
    # Datos de baja (null = activo actual)
    fecha_baja = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Fecha de baja del activo (vacío = activo actual)"
    )
    usuario_baja = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True,
        related_name='bajas_bien_afecto',
        help_text="Usuario que dio de baja el activo"
    )
    motivo_baja = models.CharField(
        max_length=20, 
        choices=MOTIVO_BAJA_CHOICES,
        null=True, 
        blank=True,
        help_text="Razón de la baja"
    )
    observaciones_baja = models.TextField(
        blank=True,
        help_text="Detalles adicionales sobre la baja"
    )
    
    @property
    def esta_activo(self):
        """Retorna True si este registro no tiene fecha de baja"""
        return self.fecha_baja is None
    
    def __str__(self):
        estado = "ACTIVO" if self.esta_activo else f"BAJA ({self.get_motivo_baja_display()})"
        return f"{self.bien_afecto.codigo_interno} - {self.activo.nombre} [{estado}]"
    
    class Meta:
        verbose_name = "Historial de Bien Afecto"
        verbose_name_plural = "Historial de Bienes Afectos"
        app_label = 'activos'
        ordering = ['-fecha_alta']
        indexes = [
            models.Index(fields=['bien_afecto', '-fecha_alta']),
            models.Index(fields=['activo']),
        ]
