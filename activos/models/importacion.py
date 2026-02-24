from django.db import models
from django.contrib.auth.models import User

class RegistroImportacion(models.Model):
    ESTADO_CHOICES = [
        ('INICIANDO', 'Iniciando'),
        ('PROCESANDO', 'En Proceso'),
        ('COMPLETADO', 'Completado'),
        ('REVERTIDO', 'Revertido'),
        ('ERROR', 'Error'),
    ]

    nombre = models.CharField(max_length=200, help_text="Nombre descriptivo de esta importación")
    tipo = models.CharField(max_length=100, default='Activos', help_text="Tipo de datos (Activos, Planos, Submittals, etc.)")
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='INICIANDO')
    
    total_filas = models.IntegerField(default=0)
    filas_nuevas = models.IntegerField(default=0)
    filas_actualizadas = models.IntegerField(default=0)
    filas_omitidas = models.IntegerField(default=0)
    filas_error = models.IntegerField(default=0)
    
    # Almacenamos los IDs creados como una lista en texto para poder revertir
    ids_creados = models.TextField(blank=True, help_text="IDs de activos creados en esta sesión (JSON)")
    
    resumen_columnas = models.JSONField(null=True, blank=True, help_text="Resumen de qué columnas se actualizaron y cuántas veces")
    
    detalles_error = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} - {self.fecha.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = "Registro de Importación"
        verbose_name_plural = "Registros de Importaciones"
        ordering = ['-fecha']
        app_label = 'activos'
