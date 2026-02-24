from django.db import models

class ControlSubmittal(models.Model):
    """
    Modelo para el control de Fichas y Submittals del proyecto (Matriz de Seguimiento).
    """
    DICTAMEN_CHOICES = [
        ('ADECUADO', 'Adecuado'),
        ('ADECUADO_CON_NOTAS', 'Adecuado con Notas'),
        ('NO_ADECUADO', 'No Adecuado'),
        ('PENDIENTE', 'Pendiente'),
    ]

    descripcion = models.TextField(null=True, blank=True, verbose_name="Descripción")
    especialidad = models.CharField(max_length=200, null=True, blank=True, verbose_name="Especialidad")
    trab_act_n = models.CharField(max_length=100, null=True, blank=True, verbose_name="TRAB-ACT-N")
    
    fecha_recibido = models.DateField(null=True, blank=True, verbose_name="Recibido")
    codigo_ficha = models.CharField(max_length=100, db_index=True, verbose_name="Código Ficha")
    codigo_submittal = models.CharField(max_length=100, db_index=True, verbose_name="Código Submittal")
    num_submittal = models.CharField(max_length=50, null=True, blank=True, verbose_name="No. Submittal")
    
    # EPC Phase
    fecha_revisado_epc = models.DateField(null=True, blank=True, verbose_name="Revisado EPC")
    comentario_epc = models.TextField(null=True, blank=True, verbose_name="Comentario EPC")
    observacion_epc = models.TextField(null=True, blank=True, verbose_name="Observación de EPC")
    
    # Supervisión Phase
    fecha_envio_sup = models.DateField(null=True, blank=True, verbose_name="Fecha Envío Sup.")
    transmision_epc_sup = models.CharField(max_length=100, null=True, blank=True, verbose_name="Transmisión EPC / SUP")
    transmision_sup_epc = models.CharField(max_length=100, null=True, blank=True, verbose_name="Transmisión SUP. / EPC")
    fecha_recepcion_sup = models.DateField(null=True, blank=True, verbose_name="Fecha Recepción Sup")
    dictamen_sup = models.CharField(max_length=100, choices=DICTAMEN_CHOICES, default='PENDIENTE', null=True, blank=True, verbose_name="Dictamen SUP")
    observacion_sup = models.TextField(null=True, blank=True, verbose_name="Observación SUP.")
    
    # Constructora / CCC Phase
    enviado_constructora = models.CharField(max_length=100, null=True, blank=True, verbose_name="Enviado a Constructora")
    fecha_envio_ccc = models.DateField(null=True, blank=True, verbose_name="Fecha Envío CCC (1)")
    
    # Estatus Centralizado
    estatus_aconex = models.CharField(max_length=100, null=True, blank=True, verbose_name="Estatus Aconex")
    estatus_ccg = models.CharField(max_length=100, null=True, blank=True, verbose_name="Estatus en CCG (ICCE)")
    
    # Archivo / Entrega
    carpeta = models.CharField(max_length=100, null=True, blank=True, verbose_name="Carpeta")
    transmitido_a_ccc = models.CharField(max_length=100, null=True, blank=True, verbose_name="Transmitido a CCC")
    fecha_envio_ccc_final = models.DateField(null=True, blank=True, verbose_name="Fecha Envío CCC (2)")

    class Meta:
        verbose_name = "Control de Submittal"
        verbose_name_plural = "Control de Submittals"
        app_label = 'activos'
        ordering = ['-fecha_recibido', 'codigo_ficha']

    def __str__(self):
        return f"{self.codigo_ficha} - {self.codigo_submittal} (Rev {self.num_submittal})"
