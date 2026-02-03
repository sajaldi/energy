from django.db import models
from colorfield.fields import ColorField
from core.storage import MinIOStorage

minio_storage = MinIOStorage()

class Plano(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='planos')
    activos = models.ManyToManyField('activos.Activo', blank=True, related_name='planos', help_text="Activos que se visualizan en este plano")
    
    # Vinculación con sistema de documentos para control de versiones
    documento = models.ForeignKey(
        'documentos.Documento',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='planos',
        help_text="Documento que contiene el archivo del plano (usa la última revisión)"
    )
    
    # Campo legacy - mantener para compatibilidad
    archivo = models.FileField(upload_to='planos/', null=True, blank=True, storage=minio_storage,
                               help_text="Archivo directo (usar 'documento' para control de versiones)")
    
    # Nuevos atributos
    TIPO_PLANO_CHOICES = [
        ('PROYECTO_EJECUTIVO', 'Proyecto Ejecutivo'),
        ('AS_BUILT', 'Plano As Built'),
        ('TALLER', 'Plano Taller'),
    ]
    tipo_plano = models.CharField(
        max_length=30, 
        choices=TIPO_PLANO_CHOICES, 
        null=True, blank=True,
        verbose_name="Tipo de Plano"
    )
    numero_documento = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="No. de Doc"
    )
    titulo = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name="Título"
    )
    disciplina = models.ForeignKey(
        'activos.Disciplina', 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='planos',
        help_text="Disciplina y Subdisciplina vinculada al plano"
    )

    descripcion = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    @property
    def archivo_actual(self):
        """Devuelve el archivo de la última revisión del documento vinculado, o el archivo directo."""
        if self.documento and self.documento.ultima_revision and self.documento.ultima_revision.archivo:
            return self.documento.ultima_revision.archivo
        return self.archivo  # Fallback al campo legacy
    
    @property
    def revision_actual(self):
        """Devuelve el identificador de revisión actual (ej: 'Rev A')"""
        if self.documento and self.documento.ultima_revision:
            return f"Rev {self.documento.ultima_revision.revision}"
        return None

    def __str__(self):
        try:
            if self.ubicacion:
                return f"{self.nombre} - {self.ubicacion.nombre}"
        except Exception:
            pass
        return f"{self.nombre} - Sin ubicación"
        
    class Meta:
        verbose_name = "Plano"
        verbose_name_plural = "Planos"
        app_label = 'activos'

class VisorPlano(models.Model):
    nombre = models.CharField(max_length=100)
    plano = models.ForeignKey(Plano, on_delete=models.CASCADE, related_name='visores')
    descripcion = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.plano.nombre})"

    class Meta:
        verbose_name = "Visor de Plano"
        verbose_name_plural = "Visores de Planos"
        app_label = 'activos'

class PinPlano(models.Model):
    visor = models.ForeignKey(VisorPlano, on_delete=models.CASCADE, related_name='pines')
    activo = models.ForeignKey('activos.Activo', on_delete=models.CASCADE, related_name='pines_planos', null=True, blank=True)
    aviso = models.ForeignKey('mantenimiento.Aviso', on_delete=models.SET_NULL, null=True, blank=True, related_name='pines_planos')
    
    # Actividad de proyecto ubicada en este punto
    actividad = models.ForeignKey(
        'proyectos.Actividad',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pines_planos',
    help_text="Actividad de proyecto ubicada en este punto"
    )
    
    # Vinculación con Ubicación (para áreas/zonas)
    ubicacion = models.ForeignKey(
        'activos.Ubicacion',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pines_planos',
        help_text="Ubicación vinculada a esta zona del plano"
    )

    x = models.FloatField(help_text="Posición X (o Left) en píxeles absolutos")
    y = models.FloatField(help_text="Posición Y (o Top) en píxeles absolutos")
    ancho = models.FloatField(default=0, help_text="Ancho del área en píxeles (0 para puntos)")
    alto = models.FloatField(default=0, help_text="Alto del área en píxeles (0 para puntos)")
    
    color = ColorField(default='#FF0000')
    nota = models.TextField(blank=True, null=True)

    def __str__(self):
        desc = self.activo.nombre if self.activo else (f"Aviso {self.aviso.id}" if self.aviso else "S/A")
        return f"Pin en {self.visor.nombre} - {desc}"

    class Meta:
        verbose_name = "Pin de Plano"
        verbose_name_plural = "Pines de Planos"
        app_label = 'activos'
        constraints = [
            models.UniqueConstraint(
                fields=['visor', 'activo'], 
                name='unique_activo_per_visor',
                condition=models.Q(activo__isnull=False)
            )
        ]

class PinFoto(models.Model):
    pin = models.ForeignKey(PinPlano, on_delete=models.CASCADE, related_name='fotos')
    imagen = models.ImageField(upload_to='pines/fotos/', storage=minio_storage)
    descripcion = models.CharField(max_length=100, blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Foto de Pin"
        verbose_name_plural = "Fotos de Pines"
        app_label = 'activos'
