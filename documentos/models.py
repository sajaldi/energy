from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
import os
import hashlib
import datetime # Required for Revision model default
from activos.models import Activo
from activos.models import Ubicacion

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

class Disciplina(models.Model):
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=10, unique=True, help_text="Abreviatura (ej: ELE, MEC)")
    
    def __str__(self):
        return self.nombre

class Documento(models.Model):
    """
    Documento Maestro. 
    Representa la entidad abstracta del documento.
    Apunta siempre a la última revisión válida.
    """
    ESTADOS = (
        ('BORRADOR', 'Borrador'),
        ('REVISION', 'En Revisión'),
        ('APROBADO', 'Aprobado'),
        ('OBSOLETO', 'Obsoleto'),
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
    
    # Metadatos de estado actual
    estado_actual = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR')
    
    # Relaciones
    activos = models.ManyToManyField(Activo, blank=True, related_name='documentos')
    ubicaciones = models.ManyToManyField(Ubicacion, blank=True, related_name='documentos')
    
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

    def __str__(self):
        return f"{self.codigo} - {self.titulo}"

    def save(self, *args, **kwargs):
        # Auto-mayúsculas para código
        if self.codigo:
            self.codigo = self.codigo.upper()
        super().save(*args, **kwargs)

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
    
    archivo = models.FileField(upload_to=documento_upload_path)
    fecha_revision = models.DateField(default=datetime.date.today)
    
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)
    
    comentarios = models.TextField(blank=True, help_text="Descripción del cambio")
    hash_archivo = models.CharField(max_length=64, blank=True, editable=False)

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
