from django.db import models
from django.contrib.auth.models import User

class Auditoria(models.Model):
    TIPO_CHOICES = [
        ('ACTIVOS', 'Por Activo (Escaneo Individual)'),
        ('CONTEO', 'Por Conteo (Masivo por Categoría)'),
    ]

    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('EN_CURSO', 'En Curso'),
        ('FINALIZADA', 'Finalizada'),
    ]

    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='ACTIVOS')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='BORRADOR')
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE)
    
    ubicaciones = models.ManyToManyField('activos.Ubicacion', related_name='auditorias', blank=True)
    categorias = models.ManyToManyField('activos.Categoria', related_name='auditorias', blank=True)

    def __str__(self):
        return f"{self.nombre} - {self.get_estado_display()}"

    class Meta:
        verbose_name = "Auditoría"
        verbose_name_plural = "Auditorías"

class ResultadoAuditoria(models.Model):
    # ... (keeps existing fields)
    ESTADO_RESULTADO = [
        ('PENDIENTE', 'Pendiente'),
        ('ENCONTRADO', 'Encontrado (Correcto)'),
        ('UBICACION_ERRONEA', 'Ubicación Errónea'),
        ('EXTRAVIADO', 'Extraviado'),
        ('NO_PERTENECE', 'No pertenece a la Auditoría'),
    ]

    auditoria = models.ForeignKey(Auditoria, on_delete=models.CASCADE, related_name='resultados')
    activo = models.ForeignKey('activos.Activo', on_delete=models.CASCADE, related_name='auditorias_participadas')
    estado = models.CharField(max_length=30, choices=ESTADO_RESULTADO, default='PENDIENTE')
    ubicacion_esperada = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, related_name='resultados_esperados')
    ubicacion_encontrada = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='resultados_reales')
    fecha_escaneo = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)

    sincronizado = models.BooleanField(default=False, verbose_name="¿Movimiento Sincronizado?")
    sincronizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sincronizaciones_auditoria')
    fecha_sincronizacion = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.auditoria} - {self.activo} ({self.estado})"

    class Meta:
        verbose_name = "Resultado de Auditoría"
        verbose_name_plural = "Resultados de Auditoría"

class ConteoAuditoria(models.Model):
    auditoria = models.ForeignKey(Auditoria, on_delete=models.CASCADE, related_name='conteos')
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.CASCADE)
    categoria = models.ForeignKey('activos.Categoria', on_delete=models.CASCADE)
    modelo = models.ForeignKey('activos.Modelo', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='conteos_auditoria', help_text="Modelo específico de activo (opcional)")
    cantidad_esperada = models.PositiveIntegerField(default=0)
    cantidad_encontrada = models.PositiveIntegerField(default=0)
    fecha_conteo = models.DateTimeField(null=True, blank=True)
    usuario_conteo = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        modelo_str = f" [{self.modelo}]" if self.modelo else ""
        return f"{self.auditoria.nombre} - {self.ubicacion} - {self.categoria}{modelo_str} ({self.cantidad_encontrada}/{self.cantidad_esperada})"

    class Meta:
        verbose_name = "Conteo de Auditoría"
        verbose_name_plural = "Conteos de Auditoría"
        unique_together = ('auditoria', 'ubicacion', 'categoria', 'modelo')
