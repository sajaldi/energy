from django.db import models
from django.contrib.auth.models import User
from colorfield.fields import ColorField


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
