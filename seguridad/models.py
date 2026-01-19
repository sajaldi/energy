from django.db import models
from django.utils import timezone

class TipoIncidente(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

class Incidente(models.Model):
    SEVERIDAD_CHOICES = [
        ('BAJA', 'Baja'),
        ('MEDIA', 'Media'),
        ('ALTA', 'Alta'),
        ('CRITICA', 'Crítica'),
    ]
    ESTADO_CHOICES = [
        ('REPORTADO', 'Reportado'),
        ('EN_PROCESO', 'En Proceso'),
        ('CERRADO', 'Cerrado'),
    ]

    titulo = models.CharField(max_length=200)
    tipo = models.ForeignKey(TipoIncidente, on_delete=models.SET_NULL, null=True)
    descripcion = models.TextField()
    fecha_ocurrencia = models.DateTimeField(default=timezone.now)
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True)
    ubicacion_texto = models.CharField(max_length=200, blank=True, help_text="Descripción manual si no hay ubicación registrada")
    reportado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='incidentes_reportados')
    severidad = models.CharField(max_length=20, choices=SEVERIDAD_CHOICES, default='BAJA')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='REPORTADO')
    foto = models.ImageField(upload_to='incidentes/', blank=True, null=True)
    
    fecha_reporte = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.titulo} - {self.get_estado_display()}"

# --- Inspecciones ---

class TipoInspeccion(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre

class ItemInspeccion(models.Model):
    tipo_inspeccion = models.ForeignKey(TipoInspeccion, on_delete=models.CASCADE, related_name='items')
    texto = models.CharField(max_length=255)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return self.texto

class Inspeccion(models.Model):
    RESULTADO_CHOICES = [
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
        ('CON_HALLAZGOS', 'Con Hallazgos'),
    ]

    tipo = models.ForeignKey(TipoInspeccion, on_delete=models.CASCADE)
    fecha = models.DateTimeField(default=timezone.now)
    inspector = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True)
    activo = models.ForeignKey('activos.Activo', on_delete=models.SET_NULL, null=True, blank=True)
    
    resultado_global = models.CharField(max_length=20, choices=RESULTADO_CHOICES, default='APROBADO')
    comentarios = models.TextField(blank=True, null=True)
    
    def __str__(self):
        objetivo = self.activo or self.ubicacion or "General"
        return f"Inspección {self.tipo} - {objetivo} ({self.fecha.date()})"

class ResultadoInspeccion(models.Model):
    ESTADO_ITEM = [
        ('CUMPLE', 'Cumple'),
        ('NO_CUMPLE', 'No Cumple'),
        ('NO_APLICA', 'No Aplica'),
    ]

    inspeccion = models.ForeignKey(Inspeccion, on_delete=models.CASCADE, related_name='resultados')
    item = models.ForeignKey(ItemInspeccion, on_delete=models.CASCADE)
    estado = models.CharField(max_length=20, choices=ESTADO_ITEM, default='CUMPLE')
    observacion = models.CharField(max_length=255, blank=True)
    foto = models.ImageField(upload_to='inspecciones/', blank=True, null=True)

# --- EPP ---

class AsignacionEPP(models.Model):
    miembro = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='epps')
    material = models.ForeignKey('inventarios.Material', on_delete=models.CASCADE, help_text="Debe ser un material de categoría EPP")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    fecha_entrega = models.DateTimeField(default=timezone.now)
    motivo = models.CharField(max_length=100, blank=True, default="Entrega Inicial")
    fecha_proxima_entrega = models.DateField(null=True, blank=True, help_text="Fecha sugerida para renovación")
    
    entregado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='epps_entregados')

    def __str__(self):
        return f"{self.material} -> {self.miembro} ({self.fecha_entrega.date()})"

# --- Analisis de Riesgos (AST) ---

class AnalisisRiesgo(models.Model):
    fecha = models.DateTimeField(default=timezone.now)
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True)
    descripcion_trabajo = models.TextField(verbose_name="Descripción del Trabajo")
    ejecutantes = models.ManyToManyField('auth.User', related_name='asts_participante')
    lider = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='asts_lider', verbose_name="Líder del Trabajo")
    firmado = models.BooleanField(default=False)

    def __str__(self):
        return f"AST - {self.descripcion_trabajo[:50]} ({self.fecha.date()})"

class PasoTrabajo(models.Model):
    analisis = models.ForeignKey(AnalisisRiesgo, on_delete=models.CASCADE, related_name='pasos')
    descripcion = models.CharField(max_length=255)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']

class Riesgo(models.Model):
    paso = models.ForeignKey(PasoTrabajo, on_delete=models.CASCADE, related_name='riesgos')
    descripcion = models.CharField(max_length=255, verbose_name="Peligro/Riesgo")

class Control(models.Model):
    riesgo = models.ForeignKey(Riesgo, on_delete=models.CASCADE, related_name='controles')
    descripcion = models.CharField(max_length=255, verbose_name="Medida de Control")

# --- Permisos de Trabajo ---

class TipoPermiso(models.Model):
    nombre = models.CharField(max_length=100) # Alturas, Caliente, Espacios Confinados
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre

class RequisitoPermiso(models.Model):
    tipo_permiso = models.ForeignKey(TipoPermiso, on_delete=models.CASCADE, related_name='requisitos')
    texto = models.CharField(max_length=255)
    es_critico = models.BooleanField(default=False, help_text="Si es crítico, no se puede proceder sin este requisito")
    orden = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['orden', 'id']

    def __str__(self):
        return self.texto

class PermisoTrabajo(models.Model):
    ESTADO_PERMISO = [
        ('BORRADOR', 'Borrador'),
        ('SOLICITADO', 'Solicitado'),
        ('APROBADO', 'Aprobado'),
        ('CERRADO', 'Cerrado/Finalizado'),
        ('CANCELADO', 'Cancelado'),
    ]

    tipo = models.ForeignKey(TipoPermiso, on_delete=models.CASCADE)
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True)
    descripcion_trabajo = models.TextField()
    
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    
    solicitante = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='permisos_solicitados')
    autorizado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='permisos_autorizados')
    fecha_autorizacion = models.DateTimeField(null=True, blank=True)
    
    estado = models.CharField(max_length=20, choices=ESTADO_PERMISO, default='BORRADOR')
    
    ast_vinculado = models.ForeignKey(AnalisisRiesgo, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="AST Vinculado")
    
    orden_trabajo = models.ForeignKey('mantenimiento.OrdenTrabajo', on_delete=models.SET_NULL, null=True, blank=True, related_name='permisos', verbose_name="Orden de Trabajo")

    def __str__(self):
        return f"Permiso {self.tipo} #{self.id} - {self.get_estado_display()}"

class VerificacionRequisito(models.Model):
    permiso = models.ForeignKey(PermisoTrabajo, on_delete=models.CASCADE, related_name='verificaciones')
    requisito = models.ForeignKey(RequisitoPermiso, on_delete=models.CASCADE)
    cumple = models.BooleanField(default=False)
    observacion = models.CharField(max_length=255, blank=True)
