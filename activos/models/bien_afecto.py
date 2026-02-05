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
    
    plano = models.ForeignKey(
        'Plano', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='bienes_afectos',
        help_text="Plano actual del bien afecto (Heredado del activo)"
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
    
    def reemplazar_activo(self, nuevo_activo, motivo_baja, usuario, observaciones=""):
        """
        Método helper para reemplazar el activo actual por uno nuevo.
        Maneja automáticamente la baja del anterior y alta del nuevo.
        
        Args:
            nuevo_activo: Instancia del nuevo Activo a asignar
            motivo_baja: Motivo de la baja (debe ser una de las opciones de MOTIVO_BAJA_CHOICES)
            usuario: Usuario que realiza el reemplazo
            observaciones: Detalles adicionales sobre el reemplazo
            
        Returns:
            Nuevo registro de HistorialBienAfecto creado
        """
        from django.utils import timezone
        
        # Dar de baja el activo actual usando update para evitar validación
        historial_actual = self.historial.filter(fecha_baja__isnull=True).first()
        if historial_actual:
            HistorialBienAfecto.objects.filter(pk=historial_actual.pk).update(
                fecha_baja=timezone.now(),
                usuario_baja=usuario,
                motivo_baja=motivo_baja,
                observaciones_baja=observaciones
            )
        
        # Dar de alta el nuevo activo
        nuevo_historial = HistorialBienAfecto.objects.create(
            bien_afecto=self,
            activo=nuevo_activo,
            usuario_alta=usuario
        )
        
        return nuevo_historial
    
    def tiempo_promedio_vida_util(self):
        """
        Calcula el tiempo promedio que duran los activos en este bien afecto.
        Retorna un timedelta o None si no hay suficientes datos.
        """
        from datetime import timedelta
        
        historiales_cerrados = self.historial.filter(fecha_baja__isnull=False)
        
        if not historiales_cerrados.exists():
            return None
        
        # Calcular duración de cada activo
        duraciones = []
        for h in historiales_cerrados:
            duracion = (h.fecha_baja - h.fecha_alta).total_seconds() / 86400  # días
            duraciones.append(duracion)
        
        promedio_dias = sum(duraciones) / len(duraciones)
        return timedelta(days=promedio_dias)
    
    def historial_completo(self):
        """
        Retorna el historial ordenado cronológicamente con información precargada.
        """
        return self.historial.select_related('activo', 'usuario_alta', 'usuario_baja').all()
    
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
    
    def clean(self):
        """
        Validaciones del modelo:
        - No puede haber más de un activo activo en el mismo bien afecto
        - Si hay fecha de baja, debe haber motivo de baja
        """
        from django.core.exceptions import ValidationError
        
        # Validar que no haya otro activo activo en el mismo bien afecto
        if not self.fecha_baja:
            activos_activos = HistorialBienAfecto.objects.filter(
                bien_afecto=self.bien_afecto,
                fecha_baja__isnull=True
            ).exclude(pk=self.pk)
            
            if activos_activos.exists():
                raise ValidationError(
                    f"Ya existe un activo activo en {self.bien_afecto.codigo_interno}. "
                    f"Debe dar de baja el activo actual antes de asignar uno nuevo."
                )
        
        # Validar que si hay fecha de baja, haya motivo
        if self.fecha_baja and not self.motivo_baja:
            raise ValidationError(
                "Debe especificar un motivo de baja cuando se da de baja un activo."
            )
    
    
    def save(self, *args, **kwargs):
        """Override save to run validations unless explicitly skipped"""
        skip_validation = kwargs.pop('skip_validation', False)
        if not skip_validation:
            self.full_clean()
        
        # Sincronizar ubicación, plano y familia con el Bien Afecto si este registro es el activo
        if self.esta_activo:
            self.bien_afecto.ubicacion = self.activo.ubicacion
            self.bien_afecto.plano = self.activo.plano
            self.bien_afecto.familia = self.activo.familia
            # Guardar BienAfecto
            self.bien_afecto.save(update_fields=['ubicacion', 'plano', 'familia'])

        super().save(*args, **kwargs)
    
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
