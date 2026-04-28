from django.db import models
from django.utils import timezone
import uuid
import datetime
from core.image_utils import compress_image


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

    def save(self, *args, **kwargs):
        if self.foto:
            self.foto = compress_image(self.foto)
        super().save(*args, **kwargs)

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

    def save(self, *args, **kwargs):
        if self.foto:
            self.foto = compress_image(self.foto)
        super().save(*args, **kwargs)


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
    TIPO_RESPUESTA_CHOICES = [
        ('INSTRUCCION', 'Instrucción (Solo lectura)'),
        ('CHECK', 'Check (Si/No/NA)'),
        ('NUMERICO', 'Valor Numérico'),
        ('TEXTO', 'Texto Libre'),
        ('FOTO', 'Registro Fotográfico'),
        ('HEADER', 'ENCABEZADO / GRUPO'),
    ]
    
    tipo_permiso = models.ForeignKey(TipoPermiso, on_delete=models.CASCADE, related_name='requisitos')
    texto = models.CharField(max_length=255)
    es_critico = models.BooleanField(default=False, help_text="Si es crítico, no se puede proceder sin este requisito")
    orden = models.PositiveIntegerField(default=0)
    
    tipo_respuesta = models.CharField(max_length=20, choices=TIPO_RESPUESTA_CHOICES, default='CHECK')
    verificacion = models.CharField(max_length=100, blank=True, null=True, help_text="¿Qué debe verificar el solicitante/autorizador?")
    
    # Metadata para validación
    unidad_medida = models.CharField(max_length=20, blank=True, null=True, help_text="Ej: ppm, %, LEL")
    valor_objetivo = models.FloatField(blank=True, null=True, help_text="Valor ideal esperado")
    rango_min = models.FloatField(blank=True, null=True)
    rango_max = models.FloatField(blank=True, null=True)
    
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
    
    valor_texto = models.TextField(blank=True, null=True)
    valor_numerico = models.FloatField(blank=True, null=True)
    valor_bool = models.BooleanField(null=True, blank=True, help_text="Para tipos CHECK")
    no_aplica = models.BooleanField(default=False)
    
    comentarios = models.TextField(blank=True, null=True, help_text="Observaciones adicionales")
    foto = models.ImageField(upload_to='permisos/verificaciones/', blank=True, null=True)
    
    capturado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.foto:
            self.foto = compress_image(self.foto)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Verificación de Requisito"
        verbose_name_plural = "Verificaciones de Requisitos"
        unique_together = ('permiso', 'requisito')

    def __str__(self):
        return f"Verif {self.permiso_id} - {self.requisito}"

# --- Confiscaciones y Levantamientos ---

class ObjetoCatalogo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Objeto de Catálogo"
        verbose_name_plural = "Catálogo de Objetos"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class LevantamientoConfiscacion(models.Model):
    fecha = models.DateTimeField(default=timezone.now)
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, verbose_name="Ubicación")
    inspector = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    comentarios = models.TextField(blank=True, null=True)
    folio = models.CharField(max_length=50, blank=True, unique=True, editable=False)
    
    finalizado = models.BooleanField(default=False, verbose_name="¿Finalizado?")
    fecha_fin = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Finalización")

    def save(self, *args, **kwargs):
        if not self.folio:
            self.folio = f"LEV-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Levantamiento de Objetos"
        verbose_name_plural = "Levantamientos de Objetos"

    def __str__(self):
        return f"{self.folio} - {self.ubicacion} ({self.fecha.date()})"

class EntregaConfiscacion(models.Model):
    nombre_retirante = models.CharField(max_length=200, verbose_name="Nombre de quien recibe")
    dni_retirante = models.CharField(max_length=50, blank=True, null=True, verbose_name="DNI/Identidad")
    
    foto_identidad = models.ImageField(upload_to='confiscaciones/entregas/id/', null=True, blank=True)
    foto_entrega = models.ImageField(upload_to='confiscaciones/entregas/evidencia/', null=True, blank=True)
    
    entregado_por = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    
    comentarios = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Entrega de Confiscación"
        verbose_name_plural = "Entregas de Confiscación"

    def save(self, *args, **kwargs):
        if self.foto_identidad:
            self.foto_identidad = compress_image(self.foto_identidad)
        if self.foto_entrega:
            self.foto_entrega = compress_image(self.foto_entrega)
        super().save(*args, **kwargs)


    def __str__(self):
        return f"Entrega #{self.id} - {self.nombre_retirante} ({self.fecha.date()})"

class ObjetoConfiscado(models.Model):
    STATUS_CHOICES = [
        ('IDENTIFICADO', 'Identificado'),
        ('TRANSITO', 'En Tránsito/Movilizando'),
        ('ALMACENADO', 'Almacenado en Bodega'),
        ('RETIRADO', 'Retirado por Tercero'),
        ('DEVUELTO', 'Devuelto/Regularizado'),
    ]

    levantamiento = models.ForeignKey(LevantamientoConfiscacion, on_delete=models.CASCADE, related_name='objetos')
    catalogo_objeto = models.ForeignKey(ObjetoCatalogo, on_delete=models.SET_NULL, null=True, verbose_name="Tipo de Objeto")
    codigo_barras = models.CharField(max_length=100, unique=True, verbose_name="Código de Barras/Etiqueta")
    descripcion = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IDENTIFICADO')
    
    fecha_confiscacion = models.DateTimeField(auto_now_add=True)
    fecha_retiro = models.DateTimeField(null=True, blank=True)
    
    # Entrega vinculada
    entrega = models.ForeignKey(EntregaConfiscacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='objetos_entregados')
    
    # Campos de Almacén
    comentario_almacen = models.TextField(null=True, blank=True, verbose_name="Comentario de Almacén/Discrepancia")
    ubicacion_almacen = models.CharField(max_length=100, null=True, blank=True, verbose_name="Ubicación en Bodega")

    @property
    def tiene_novedad_almacen(self):
        """ Retorna True si el objeto tiene comentarios o fotos de la etapa Almacén """
        if self.comentario_almacen:
            return True
        return self.fotos.filter(etapa='ALMACEN').exists()

    class Meta:
        verbose_name = "Objeto Confiscado"
        verbose_name_plural = "Objetos Confiscados"

    def __str__(self):
        return f"{self.catalogo_objeto} [{self.codigo_barras}]"

class FotoObjetoConfiscado(models.Model):
    ETAPA_CHOICES = [
        ('LEVANTE', 'Levantamiento'),
        ('ALMACEN', 'Recepción Almacén'),
        ('RETIRO', 'Retiro/Cierre')
    ]
    objeto = models.ForeignKey(ObjetoConfiscado, on_delete=models.CASCADE, related_name='fotos')
    foto = models.ImageField(upload_to='confiscaciones/')
    etapa = models.CharField(max_length=20, choices=ETAPA_CHOICES, default='LEVANTE')
    creado_en = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.foto:
            self.foto = compress_image(self.foto)
        super().save(*args, **kwargs)

    class Meta:

        verbose_name = "Foto de Objeto"
        verbose_name_plural = "Fotos de Objetos"
