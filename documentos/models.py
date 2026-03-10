from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from pgvector.django import VectorField
import os
import hashlib
import datetime # Required for Revision model default
from activos.models import Activo
from activos.models import Ubicacion
from core.storage import MinIOStorage

minio_storage = MinIOStorage()

def documento_upload_path(instance, filename):
    # Organizar por Año/Mes para evitar carpetas gigantes
    # instance es Revision
    import datetime
    now = datetime.datetime.now()
    return 'docs/{}/{}/{}/{}'.format(now.year, now.month, instance.documento.codigo, filename)

class TipoDocumento(models.Model):
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=10, unique=True, help_text="Abreviatura para códigos (ej: PLN, MNL)")
    
    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Tipo de Documento"
        verbose_name_plural = "Tipos de Documento"

class MetadatoConfig(models.Model):
    """
    Configuración de campos dinámicos asociados a un Tipo de Documento.
    """
    TIPOS_CAMPO = (
        ('TEXTO', 'Texto'),
        ('EMAIL', 'Email'),
        ('FECHA', 'Fecha'),
        ('HORA', 'Hora'),
        ('NUMERO', 'Número'),
        ('URL', 'URL'),
        ('RELACION', 'Relación con otro Modelo'),
    )
    
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.CASCADE, related_name='metadatos_config')
    nombre = models.CharField(max_length=50, help_text="Nombre interno del campo (ej: fecha_vencimiento)")
    etiqueta = models.CharField(max_length=100, help_text="Nombre que verá el usuario (ej: Fecha de Vencimiento)")
    tipo_campo = models.CharField(max_length=20, choices=TIPOS_CAMPO, default='TEXTO')
    requerido = models.BooleanField(default=False)
    
    # Campo para vinculación con otros modelos
    from django.contrib.contenttypes.models import ContentType
    modelo_relativo = models.ForeignKey(
        ContentType, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Si el tipo es RELACION, seleccione a qué tabla apunta."
    )
    
    campo_visualizacion = models.CharField(
        max_length=50, 
        blank=True, 
        default='', 
        help_text="Si el tipo es RELACION, nombre del campo a mostrar (ej: 'nombre', 'codigo'). Dejar vacío para usar el valor por defecto."
    )
    
    descripcion = models.TextField(
        blank=True, 
        default='',
        help_text="Instrucciones para la IA: dónde o cómo extraer este campo del documento (ej: 'Buscar en el encabezado, después de Asunto:')"
    )
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Configuración de Metadato"
        verbose_name_plural = "Configuraciones de Metadatos"
        ordering = ['orden']
        unique_together = ('tipo_documento', 'nombre')

    def __str__(self):
        return f"{self.tipo_documento.nombre} - {self.etiqueta} ({self.tipo_campo})"

class Disciplina(models.Model):
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=10, unique=True, help_text="Abreviatura (ej: ELE, MEC)")
    
    def __str__(self):
        return self.nombre

class N8nChatHistory(models.Model):
    """
    Historial de conversaciones con el chat de IA (n8n).
    Almacena mensajes del usuario y respuestas de la IA para mantener contexto.
    """
    session_id = models.CharField(
        max_length=100, 
        db_index=True,
        help_text="ID de sesión para agrupar mensajes de una conversación"
    )
    usuario = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='chat_histories'
    )
    documento = models.ForeignKey(
        'Documento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_histories',
        help_text="Documento sobre el que se está conversando (opcional)"
    )
    
    # Mensaje
    mensaje_usuario = models.TextField(help_text="Pregunta o mensaje del usuario")
    respuesta_ia = models.TextField(help_text="Respuesta generada por la IA")
    
    # Metadata
    timestamp = models.DateTimeField(auto_now_add=True)
    tokens_usados = models.IntegerField(null=True, blank=True, help_text="Tokens consumidos en esta interacción")
    modelo = models.CharField(max_length=50, blank=True, help_text="Modelo de IA utilizado (ej: gpt-4)")
    
    class Meta:
        verbose_name = "Historial de Chat IA"
        verbose_name_plural = "Historiales de Chat IA"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['session_id', '-timestamp']),
            models.Index(fields=['usuario', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.usuario.username} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class Documento(models.Model):
    """
    Documento Maestro. 
    Representa la entidad abstracta del documento.
    Apunta siempre a la última revisión válida.
    """
    ESTADOS = (
        ('RECIBIDO', 'Recibido'),
        ('EN_PROCESO', 'En Proceso'),
        ('NO_CONTESTADO', 'No Contestado'),
        ('COMPLETADO', 'Completado'),
    )

    codigo = models.CharField(
        _("Código"), 
        max_length=50, 
        unique=True,
        help_text="Código único del documento (Ej: CCG-I-T1-IAA-07-02)"
    )
    titulo = models.CharField(_("Título"), max_length=255)
    
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.PROTECT, verbose_name=_("Tipo"))
    disciplina = models.ForeignKey(Disciplina, on_delete=models.PROTECT, null=True, blank=True)
    
    # Trazabilidad
    respuesta_a = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='respuestas',
        verbose_name=_("Respuesta a"),
        help_text="Documento al que este archivo hace referencia o responde."
    )
    
    # Metadatos de estado actual
    estado_actual = models.CharField(max_length=20, choices=ESTADOS, default='RECIBIDO')
    
    # Relaciones
    activos = models.ManyToManyField(Activo, blank=True, related_name='documentos')
    ubicaciones = models.ManyToManyField(Ubicacion, blank=True, related_name='documentos')
    
    responsable = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='documentos_responsable',
        verbose_name=_("Responsable")
    )
    
    # Cache de la última revisión para acceso rápido
    ultima_revision = models.ForeignKey(
        'Revision', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='documento_actual',
        verbose_name=_("Última Revisión")
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # Campo para búsqueda por contenido
    contenido_texto = models.TextField(
        _("Contenido Texto"), 
        blank=True, 
        null=True,
        help_text="Texto extraído del documento para búsquedas."
    )

    fecha_inicio = models.DateField(
        _("Fecha Inicio/Emisión"), 
        blank=True, 
        null=True,
        help_text="Fecha de inicio o emisión del documento."
    )

    fecha_vencimiento = models.DateField(
        _("Fecha de Vencimiento"), 
        blank=True, 
        null=True,
        help_text="Fecha en que expira la validez del documento."
    )
    
    # Campo para búsqueda vectorial semántica
    embedding = VectorField(dimensions=384, null=True, blank=True)

    def __str__(self):
        return f"{self.codigo} - {self.titulo}"

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['estado_actual']),
            models.Index(fields=['creado_en']),
        ]

    def save(self, *args, **kwargs):
        # Auto-mayúsculas para código
        if self.codigo:
            self.codigo = self.codigo.upper()
        super().save(*args, **kwargs)
    
    @classmethod
    def buscar_por_contenido(cls, query):
        """
        Búsqueda de texto completo en el contenido extraído.
        Usa PostgreSQL Full-Text Search para búsquedas rápidas.
        """
        from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
        
        search_vector = SearchVector('contenido_texto', config='spanish')
        search_query = SearchQuery(query, config='spanish')
        
        return cls.objects.annotate(
            search=search_vector,
            rank=SearchRank(search_vector, search_query)
        ).filter(search=search_query).order_by('-rank')


class DocumentoFragmento(models.Model):
    """
    Representa un fragmento de texto de un documento para búsqueda vectorial.
    Permite indexar documentos largos dividiéndolos en partes más pequeñas.
    """
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name='fragmentos')
    contenido = models.TextField()
    embedding = VectorField(dimensions=384, null=True, blank=True)
    orden = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = "Fragmento de Documento"
        verbose_name_plural = "Fragmentos de Documentos"
        ordering = ['documento', 'orden']
        indexes = [
            models.Index(fields=['documento']),
        ]

    def __str__(self):
        return f"Fragmento {self.orden} de {self.documento.codigo}"


class MetadatoValor(models.Model):
    """
    Almacena el valor de un metadato dinámico para un documento específico.
    Soporta valores de texto y vínculos relacionales genéricos.
    """
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name='metadatos_valores')
    config = models.ForeignKey(MetadatoConfig, on_delete=models.CASCADE)
    valor = models.TextField(blank=True, null=True)
    
    # --- Soporte para Relaciones Genéricas (KPI, Activos, etc.) ---
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.contenttypes.fields import GenericForeignKey
    
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    objeto_vinculado = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = "Valor de Metadato"
        verbose_name_plural = "Valores de Metadatos"
        unique_together = ('documento', 'config')

    def __str__(self):
        if self.objeto_vinculado:
            return f"{self.documento.codigo}: {self.config.etiqueta} -> {self.objeto_vinculado}"
        return f"{self.documento.codigo}: {self.config.etiqueta} = {self.valor}"

    def save(self, *args, **kwargs):
        # Si es un metadato de tipo RELACIÓN y tiene una configuración de modelo
        if self.config.tipo_campo == 'RELACION' and self.config.modelo_relativo:
            # Sincronizar ContentType desde la configuración si no está definido
            if not self.content_type:
                self.content_type = self.config.modelo_relativo
        
        super().save(*args, **kwargs)

class ComentarioDocumento(models.Model):
    """
    Comentarios u observaciones asociados a un punto específico del PDF.
    """
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name='comentarios')
    revision = models.ForeignKey('Revision', on_delete=models.CASCADE, related_name='comentarios_pines', null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    texto = models.TextField()
    
    # Posicionamiento (Pins y Áreas)
    TIPO_COMENTARIO = (
        ('PIN', 'Pin (Punto)'),
        ('AREA', 'Área (Rectángulo)'),
    )
    tipo = models.CharField(max_length=10, choices=TIPO_COMENTARIO, default='PIN')
    posicion_x = models.FloatField(default=0, help_text="Posición X en porcentaje (0-100)")
    posicion_y = models.FloatField(default=0, help_text="Posición Y en porcentaje (0-100)")
    ancho = models.FloatField(default=0, help_text="Ancho en porcentaje (0-100) para áreas")
    alto = models.FloatField(default=0, help_text="Alto en porcentaje (0-100) para áreas")
    pagina = models.PositiveIntegerField(default=1)
    
    creado_en = models.DateTimeField(auto_now_add=True)
    resuelto = models.BooleanField(default=False, help_text="Marcar si el comentario ya ha sido atendido")
    
    # Vínculos entre pines (Navegación entre documentos)
    vinculos = models.ManyToManyField('self', blank=True, symmetrical=True, help_text="Pines relacionados en otros documentos")
    
    # Responsable de la tarea (Asignación)
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='comentarios_asignados', help_text="Usuario asignado para resolver este comentario")

    class Meta:
        verbose_name = "Comentario de Documento"
        verbose_name_plural = "Comentarios de Documentos"
        ordering = ['-creado_en']

    def __str__(self):
        return f"Comentario de {self.usuario.username} en {self.documento.codigo} (Hoja {self.pagina})"

def comentario_imagen_path(instance, filename):
    return 'comentarios/pins/{}/{}'.format(instance.comentario.id, filename)

class ComentarioImagen(models.Model):
    """
    Imágenes o fotos adjuntas a un comentario/pin.
    """
    comentario = models.ForeignKey(ComentarioDocumento, on_delete=models.CASCADE, related_name='imagenes')
    imagen = models.ImageField(upload_to=comentario_imagen_path, storage=minio_storage)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Imagen de Comentario"
        verbose_name_plural = "Imágenes de Comentarios"

    def __str__(self):
        return f"Imagen de Pin {self.comentario.id} - {self.id}"


class Revision(models.Model):
    """
    Revisiones históricas del documento.
    Cada carga de archivo genera una nueva instancia aquí.
    """
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name='revisiones')
    
    revision = models.CharField(
        _("Revisión"), 
        max_length=10, 
        help_text="Ej: A, B, 0, 1, 2..."
    )
    
    archivo = models.FileField(upload_to=documento_upload_path, storage=minio_storage, max_length=255)
    fecha_revision = models.DateField(default=datetime.date.today)
    
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)
    
    comentarios = models.TextField(blank=True, help_text="Descripción del cambio")
    hash_archivo = models.CharField(max_length=64, blank=True, editable=False)

    # --- Campos para Extracción de Datos ---
    estado_extraccion = models.CharField(
        max_length=20,
        choices=(
            ('PENDIENTE', 'Pendiente'),
            ('PROCESANDO', 'Procesando'),
            ('COMPLETADO', 'Completado'),
            ('ERROR', 'Error'),
            ('NO_APLICA', 'No Aplica'),
        ),
        default='PENDIENTE'
    )
    datos_extraidos = models.JSONField(null=True, blank=True)

    def get_proxy_url(self):
        """Retorna la URL directa del archivo"""
        if not self.archivo:
            return ""
        return self.archivo.url

    @property
    def url_proxy(self):
        return self.get_proxy_url()

    class Meta:
        verbose_name = "Revisión"
        verbose_name_plural = "Revisiones"
        ordering = ['-creado_en']
        unique_together = ('documento', 'revision')

    def __str__(self):
        return f"{self.documento.codigo} - Rev {self.revision}"

    def save(self, *args, **kwargs):
        # Calcular Hash MD5 si hay archivo nuevo
        if self.archivo and not self.hash_archivo:
             # Nota: Calcular hash requiere leer el archivo, se puede hacer aquí o en una señal/form
             # Por simplicidad ahora lo dejamos pendiente o implementamos básico
             pass
        super().save(*args, **kwargs)
        
        # Actualizar el puntero del documento maestro tras crear una revisión reciente
        # Esto es lógica de negocio simple, idealmente comprobar fechas/versión
        if not self.documento.ultima_revision or self.creado_en >= self.documento.ultima_revision.creado_en:
             self.documento.ultima_revision = self
             self.documento.save()

class Biblioteca(models.Model):
    """
    Colección de documentos agrupados temáticamente.
    Relación muchos a muchos con Documento.
    """
    nombre = models.CharField(_("Nombre"), max_length=200)
    descripcion = models.TextField(_("Descripción"), blank=True, null=True)
    documentos = models.ManyToManyField(
        Documento,
        blank=True,
        related_name='bibliotecas',
        verbose_name=_("Documentos")
    )
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bibliotecas_creadas',
        verbose_name=_("Creado por")
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Biblioteca"
        verbose_name_plural = "Bibliotecas"
        ordering = ['-actualizado_en']

    def __str__(self):
        return self.nombre

    def cantidad_documentos(self):
        return self.documentos.count()
    cantidad_documentos.short_description = "Documentos"


# Importar modelos del sistema de firmas electrónicas
from .models_firmas import (
    PerfilFirma,
    DocumentoFirmado,
    FirmaRequerida,
    Firma,
    AuditoriaFirmas
)

