from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
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
    )
    
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.CASCADE, related_name='metadatos_config')
    nombre = models.CharField(max_length=50, help_text="Nombre interno del campo (ej: fecha_vencimiento)")
    etiqueta = models.CharField(max_length=100, help_text="Nombre que verá el usuario (ej: Fecha de Vencimiento)")
    tipo_campo = models.CharField(max_length=20, choices=TIPOS_CAMPO, default='TEXTO')
    requerido = models.BooleanField(default=False)
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
        ('BORRADOR', 'Borrador'),
        ('ENVIADO', 'Enviado'),
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
    estado_actual = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR')
    
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

    def __str__(self):
        return f"{self.codigo} - {self.titulo}"

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['estado_actual']),
            models.Index(fields=['creado_en']),
            # Índice GIN para búsqueda de texto completo en PostgreSQL
            models.Index(
                name='contenido_texto_gin_idx',
                fields=['contenido_texto'],
                opclasses=['gin_trgm_ops']
            ),
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


class MetadatoValor(models.Model):
    """
    Almacena el valor de un metadato dinámico para un documento específico.
    """
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name='metadatos_valores')
    config = models.ForeignKey(MetadatoConfig, on_delete=models.CASCADE)
    valor = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Valor de Metadato"
        verbose_name_plural = "Valores de Metadatos"
        unique_together = ('documento', 'config')

    def __str__(self):
        return f"{self.documento.codigo}: {self.config.etiqueta} = {self.valor}"

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
    
    archivo = models.FileField(upload_to=documento_upload_path, storage=minio_storage)
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

# Importar modelos del sistema de firmas electrónicas
from .models_firmas import (
    PerfilFirma,
    DocumentoFirmado,
    FirmaRequerida,
    Firma,
    AuditoriaFirmas
)

# --- Integración Mayan EDMS ---
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class MayanDocumentLink(models.Model):
    """
    Vincula documentos de Mayan EDMS con cualquier modelo de Django
    usando Generic Foreign Keys
    """
    # Documento en Mayan
    mayan_document_id = models.IntegerField(
        help_text="ID del documento en Mayan EDMS"
    )
    document_label = models.CharField(
        max_length=255,
        help_text="Nombre/etiqueta del documento"
    )
    document_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Tipo de documento (Manual, Certificado, etc.)"
    )
    
    # Vinculación genérica con cualquier modelo
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Metadatos
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Vínculo de Documento Mayan"
        verbose_name_plural = "Vínculos de Documentos Mayan"
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['mayan_document_id']),
        ]
    
    def __str__(self):
        return f"{self.document_label} -> {self.content_object}"
    
    @property
    def mayan_url(self):
        """URL para ver el documento en Mayan"""
        from django.conf import settings
        return f"{settings.MAYAN_EDMS_URL}/documents/{self.mayan_document_id}/"
    
    @property
    def download_url(self):
        """URL para descargar el documento"""
        from .mayan_client import MayanEDMSClient
        client = MayanEDMSClient()
        return client.get_document_file_url(self.mayan_document_id)
