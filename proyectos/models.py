from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_delete
from django.dispatch import receiver
from colorfield.fields import ColorField
from core.storage import MinIOStorage

minio_storage = MinIOStorage()


class Proyecto(models.Model):
    """
    Modelo principal de Proyecto.
    Contiene documentos y actividades asociadas.
    """
    ESTADOS = (
        ('PLANIFICACION', 'En Planificación'),
        ('EJECUCION', 'En Ejecución'),
        ('PAUSADO', 'Pausado'),
        ('COMPLETADO', 'Completado'),
        ('CANCELADO', 'Cancelado'),
    )
    
    codigo = models.CharField(
        max_length=50, 
        unique=True, 
        blank=True,
        help_text="Código único del proyecto (se genera automáticamente si se deja vacío, formato: PROY-YYYY-NNNN)"
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    nota = models.TextField(blank=True, help_text="Notas internas del proyecto")
    
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PLANIFICACION')
    
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin_estimada = models.DateField(null=True, blank=True)
    
    responsable = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='proyectos_responsable'
    )
    ubicacion = models.ForeignKey(
        'activos.Ubicacion', 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='proyectos'
    )
    
    # Visores de planos asociados al proyecto
    visores = models.ManyToManyField(
        'activos.VisorPlano',
        blank=True,
        related_name='proyectos',
        help_text="Visores de plano para ubicar actividades del proyecto"
    )
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-generar código si está vacío
        if not self.codigo:
            from django.utils import timezone
            # Formato: PROY-YYYY-NNNN (ej: PROY-2026-0001)
            year = timezone.now().year
            # Buscar el último proyecto del año
            last_project = Proyecto.objects.filter(
                codigo__startswith=f'PROY-{year}-'
            ).order_by('-codigo').first()
            
            if last_project:
                # Extraer el número del último código
                try:
                    last_num = int(last_project.codigo.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            # Generar código con padding de 4 dígitos
            self.codigo = f'PROY-{year}-{next_num:04d}'
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    @property
    def total_actividades(self):
        return self.actividades.count()
    
    @property
    def actividades_completadas(self):
        return self.actividades.filter(estado='COMPLETADA').count()
    
    @property
    def porcentaje_avance(self):
        total = self.total_actividades
        if total == 0:
            return 0
        return int((self.actividades_completadas / total) * 100)

    class Meta:
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"
        ordering = ['-creado_en']


class DocumentoProyecto(models.Model):
    """
    Relación entre Proyecto y Documento.
    Permite agregar documentos como inline en el admin.
    """
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name='documentos_proyecto'
    )
    documento = models.ForeignKey(
        'documentos.Documento',
        on_delete=models.CASCADE,
        related_name='proyectos_vinculados'
    )
    carpeta = models.ForeignKey(
        'documentos.Carpeta',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vinculos_proyectos'
    )
    nota = models.CharField(max_length=200, blank=True, help_text="Nota o descripción del documento en este proyecto")
    agregado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.proyecto.codigo} - {self.documento.codigo}"

    class Meta:
        verbose_name = "Documento del Proyecto"
        verbose_name_plural = "Documentos del Proyecto"
        unique_together = ('proyecto', 'documento')


class ObservacionProyecto(models.Model):
    ESTADOS = (
        ('ABIERTA', 'Abierta'),
        ('EN_PROCESO', 'En Proceso'),
        ('RESUELTA', 'Resuelta'),
        ('CERRADA', 'Cerrada'),
    )

    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name='observaciones',
        verbose_name="Proyecto"
    )
    documento_proyecto = models.ForeignKey(
        DocumentoProyecto,
        on_delete=models.CASCADE,
        related_name='observaciones',
        verbose_name="Documento del proyecto",
        null=True,
        blank=True,
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='observaciones_proyecto',
        verbose_name="Creado por"
    )
    observacion = models.TextField(verbose_name="Observación")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ABIERTA', verbose_name="Estado")
    fecha_observacion = models.DateField(verbose_name="Fecha de observación")
    fecha_resolucion = models.DateField(null=True, blank=True, verbose_name="Fecha de resolución")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Observación de Proyecto"
        verbose_name_plural = "Observaciones de Proyecto"
        ordering = ['-fecha_observacion']

    def __str__(self):
        return f"[{self.get_estado_display()}] {self.documento_proyecto.documento.codigo} - {self.observacion[:60]}"


class Actividad(models.Model):
    """
    Actividad dentro de un proyecto.
    Puede ser ubicada en un pin de plano.
    """
    ESTADOS = (
        ('PENDIENTE', 'Pendiente'),
        ('EN_PROGRESO', 'En Progreso'),
        ('COMPLETADA', 'Completada'),
        ('BLOQUEADA', 'Bloqueada'),
    )
    PRIORIDADES = (
        ('BAJA', 'Baja'),
        ('MEDIA', 'Media'),
        ('ALTA', 'Alta'),
        ('CRITICA', 'Crítica'),
    )
    
    proyecto = models.ForeignKey(
        Proyecto, 
        on_delete=models.CASCADE, 
        related_name='actividades'
    )
    
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    prioridad = models.CharField(max_length=20, choices=PRIORIDADES, default='MEDIA')
    
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    porcentaje_avance = models.PositiveIntegerField(default=0, help_text="Porcentaje de avance (0-100)")
    
    asignado_a = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='actividades_asignadas'
    )
    
    predecesora = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sucesoras',
        verbose_name="Actividad Predecesora"
    )
    
    orden = models.PositiveIntegerField(default=0, help_text="Orden de ejecución")
    
    color = ColorField(default='#3B82F6', help_text="Color para identificar en planos")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    ordenes_trabajo = models.ManyToManyField(
        'mantenimiento.OrdenTrabajo',
        blank=True,
        related_name='actividades_proyecto',
        verbose_name="Órdenes de Trabajo"
    )

    def __str__(self):
        return f"{self.proyecto.codigo} - {self.nombre}"

    class Meta:
        verbose_name = "Actividad"
        verbose_name_plural = "Actividades"
        ordering = ['proyecto', 'orden', 'creado_en']


class PlanoProyecto(models.Model):
    """
    Plano PDF asociado a un proyecto.
    Almacena archivos PDF en MinIO para documentación técnica del proyecto.
    """
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name='planos_pdf'
    )
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    archivo = models.FileField(
        upload_to='proyectos/planos/',
        storage=minio_storage,
        max_length=500
    )
    subido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    fecha_carga = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plano de Proyecto"
        verbose_name_plural = "Planos de Proyecto"
        ordering = ['-fecha_carga']

    def __str__(self):
        return f"{self.proyecto.codigo} - {self.titulo}"


class PinObservacionProyecto(models.Model):
    """
    Pin que vincula una observación de proyecto a una posición específica
    en un plano PDF del mismo proyecto.
    """
    plano = models.ForeignKey(
        PlanoProyecto,
        on_delete=models.CASCADE,
        related_name='pines_observacion'
    )
    observacion = models.ForeignKey(
        ObservacionProyecto,
        on_delete=models.CASCADE,
        related_name='pines_plano'
    )
    coordenada_x = models.FloatField(help_text="Posición X en puntos PDF intrínsecos (viewport scale=1)")
    coordenada_y = models.FloatField(help_text="Posición Y en puntos PDF intrínsecos (viewport scale=1)")
    pagina = models.PositiveIntegerField(default=1)
    color = ColorField(default='#EF4444')
    nota = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('plano', 'observacion')
        verbose_name = "Pin de Observación en Proyecto"
        verbose_name_plural = "Pines de Observación en Proyecto"

    def __str__(self):
        return f"Pin en {self.plano.titulo} - {self.observacion.observacion[:50]}"


class FotoPinObservacion(models.Model):
    """Foto adjunta a un pin de observación en un plano de proyecto."""
    pin = models.ForeignKey(
        PinObservacionProyecto,
        on_delete=models.CASCADE,
        related_name='fotos'
    )
    imagen = models.ImageField(upload_to='proyectos/fotos_pines/')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['creado_en']
        verbose_name = "Foto de Pin de Observación"
        verbose_name_plural = "Fotos de Pin de Observación"

    def save(self, *args, **kwargs):
        if self.imagen:
            from core.image_utils import compress_image
            self.imagen = compress_image(self.imagen)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Foto {self.id} - Pin {self.pin_id}"


class AreaPlanoProyecto(models.Model):
    """Área rectangular definida sobre una página del plano de proyecto."""
    plano = models.ForeignKey(
        PlanoProyecto,
        on_delete=models.CASCADE,
        related_name='areas'
    )
    nombre = models.CharField(max_length=100)
    color = ColorField(default='#3B82F6')
    x1 = models.FloatField(help_text="X esquina superior izquierda (puntos PDF intrínsecos, scale=1)")
    y1 = models.FloatField(help_text="Y esquina superior izquierda (puntos PDF intrínsecos, scale=1)")
    x2 = models.FloatField(help_text="X esquina inferior derecha (puntos PDF intrínsecos, scale=1)")
    y2 = models.FloatField(help_text="Y esquina inferior derecha (puntos PDF intrínsecos, scale=1)")
    pagina = models.PositiveIntegerField(default=1)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['creado_en']
        verbose_name = "Área de Plano de Proyecto"
        verbose_name_plural = "Áreas de Plano de Proyecto"

    def __str__(self):
        return f"{self.nombre} - {self.plano.titulo} (p.{self.pagina})"


@receiver(post_delete, sender=PlanoProyecto)
def eliminar_archivo_plano(sender, instance, **kwargs):
    if instance.archivo:
        try:
            instance.archivo.delete(save=False)
        except Exception:
            pass


class ElementoProyecto(models.Model):
    ESTADOS = (
        ('PENDIENTE', 'Pendiente'),
        ('EN_PROCESO', 'En Proceso'),
        ('COMPLETADO', 'Completado'),
        ('CANCELADO', 'Cancelado'),
    )

    proyecto = models.ForeignKey(
        Proyecto, on_delete=models.CASCADE,
        related_name='elementos', verbose_name="Proyecto"
    )
    item_cotizacion = models.ForeignKey(
        'presupuestos.ItemCotizacion', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='elementos_proyecto',
        verbose_name="Item de Cotización"
    )
    nombre = models.CharField(max_length=300, verbose_name="Nombre del elemento")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE', verbose_name="Estado")
    fecha_ejecucion_inicio = models.DateField(null=True, blank=True, verbose_name="Fecha inicio ejecución")
    fecha_ejecucion_fin = models.DateField(null=True, blank=True, verbose_name="Fecha fin ejecución")
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=1, verbose_name="Cantidad")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Elemento de Proyecto"
        verbose_name_plural = "Elementos del Proyecto"
        ordering = ['orden', 'creado_en']

    def __str__(self):
        return f"{self.proyecto.codigo} - {self.nombre}"


class ElementoDocumento(models.Model):
    elemento = models.ForeignKey(
        ElementoProyecto, on_delete=models.CASCADE,
        related_name='documentos', verbose_name="Elemento"
    )
    archivo = models.FileField(
        upload_to='proyectos/elementos/',
        storage=minio_storage,
        max_length=500,
        verbose_name="Archivo / Foto"
    )
    descripcion = models.CharField(max_length=300, blank=True, verbose_name="Descripción")
    tipo = models.CharField(
        max_length=20, default='FOTO',
        choices=[('FOTO', 'Foto'), ('DOCUMENTO', 'Documento'), ('OTRO', 'Otro')],
        verbose_name="Tipo"
    )
    subido_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Subido por"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Documento de Elemento"
        verbose_name_plural = "Documentos del Elemento"
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.elemento.nombre} - {self.descripcion or 'Sin descripción'}"  # Si falla la eliminación del archivo, no bloquear la operación
