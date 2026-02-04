"""
Sistema de Firmas Electrónicas
--------------------------------
Proporciona un sistema completo de firmas electrónicas con:
- Firmas manuscritas (canvas)
- Subida de imágenes PNG de firmas
- Posicionamiento flexible en documentos
- Hash criptográfico para integridad
- Trazabilidad completa
- Validación de autenticidad
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.utils import timezone
import hashlib
import uuid
from io import BytesIO
from PIL import Image
from core.storage import MinIOStorage

minio_storage = MinIOStorage()


def firma_upload_path(instance, filename):
    """Ruta de almacenamiento para firmas subidas"""
    ext = filename.split('.')[-1]
    filename = f"{instance.usuario.username}_{uuid.uuid4().hex[:8]}.{ext}"
    return f'firmas/usuarios/{instance.usuario.id}/{filename}'


def firma_documento_path(instance, filename):
    """Ruta de almacenamiento para firmas estampadas en documentos"""
    return f'firmas/documentos/{instance.documento_firmado.documento.codigo}/{filename}'


class PerfilFirma(models.Model):
    """
    Perfil de firma de un usuario.
    Permite almacenar una firma manuscrita o subida como PNG
    para reutilización en múltiples documentos.
    """
    usuario = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='perfil_firma',
        verbose_name="Usuario"
    )
    
    # La firma puede ser manuscrita (canvas) o una imagen PNG subida
    firma_imagen = models.ImageField(
        upload_to=firma_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['png', 'jpg', 'jpeg'])],
        help_text="Imagen de la firma (PNG recomendado con fondo transparente)",
        blank=True,
        null=True,
        storage=minio_storage
    )
    
    # Metadatos
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)
    activa = models.BooleanField(
        default=True,
        help_text="Si está activa, esta firma se usará por defecto"
    )
    
    # Información adicional del firmante
    cargo = models.CharField(max_length=200, blank=True, help_text="Cargo del firmante")
    departamento = models.CharField(max_length=200, blank=True)
    
    class Meta:
        verbose_name = "Perfil de Firma"
        verbose_name_plural = "Perfiles de Firma"
    
    def __str__(self):
        return f"Firma de {self.usuario.get_full_name() or self.usuario.username}"
    
    def generar_hash_firma(self):
        """Genera un hash SHA-256 de la imagen de firma para verificación"""
        if not self.firma_imagen:
            return None
        
        self.firma_imagen.seek(0)
        img_data = self.firma_imagen.read()
        return hashlib.sha256(img_data).hexdigest()


class DocumentoFirmado(models.Model):
    """
    Representa un documento que ha sido firmado.
    Contiene el hash del documento original para verificación de integridad.
    """
    # Relación con el documento de la app documentos
    from documentos.models import Revision
    
    documento = models.ForeignKey(
        'documentos.Documento',
        on_delete=models.CASCADE,
        related_name='firmas_aplicadas',
        verbose_name="Documento"
    )
    
    revision = models.ForeignKey(
        'documentos.Revision',
        on_delete=models.CASCADE,
        related_name='firmas',
        verbose_name="Revisión del Documento",
        null=True,
        blank=True
    )
    
    # Hash SHA-256 del archivo original (para verificar que no ha sido modificado)
    hash_documento_original = models.CharField(
        max_length=64,
        editable=False,
        help_text="Hash SHA-256 del documento en el momento de la firma"
    )
    
    # Estado del documento firmado
    ESTADOS = (
        ('PENDIENTE', 'Pendiente de Firmas'),
        ('PARCIAL', 'Firmado Parcialmente'),
        ('COMPLETO', 'Firmado Completamente'),
        ('RECHAZADO', 'Rechazado'),
    )
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    
    # Metadatos
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    
    # Archivo PDF con firmas estampadas (generado después de firmar)
    pdf_firmado = models.FileField(
        upload_to='firmas/documentos_firmados/',
        blank=True,
        null=True,
        help_text="PDF con todas las firmas estampadas",
        storage=minio_storage
    )
    
    class Meta:
        verbose_name = "Documento Firmado"
        verbose_name_plural = "Documentos Firmados"
        ordering = ['-creado_en']
    
    def __str__(self):
        return f"{self.documento.codigo} - Firmado ({self.estado})"
    
    def calcular_hash_documento(self):
        """Calcula el hash SHA-256 del documento original"""
        if self.revision and self.revision.archivo:
            archivo = self.revision.archivo
            archivo.seek(0)
            hash_obj = hashlib.sha256()
            
            # Leer en chunks para archivos grandes
            for chunk in archivo.chunks():
                hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
        return None
    
    def save(self, *args, **kwargs):
        # Calcular hash del documento si no existe
        if not self.hash_documento_original and self.revision:
            self.hash_documento_original = self.calcular_hash_documento() or ""
        
        super().save(*args, **kwargs)
        
        # Actualizar estado basado en firmas
        self.actualizar_estado()
    
    def actualizar_estado(self):
        """Actualiza el estado basado en las firmas aplicadas"""
        firmas_requeridas = self.firmas_requeridas.count()
        firmas_aplicadas = self.firmas.filter(firmado=True, rechazado=False).count()
        firmas_rechazadas = self.firmas.filter(rechazado=True).count()
        
        if firmas_rechazadas > 0:
            self.estado = 'RECHAZADO'
        elif firmas_requeridas == 0:
            self.estado = 'PENDIENTE'
        elif firmas_aplicadas == firmas_requeridas:
            self.estado = 'COMPLETO'
        elif firmas_aplicadas > 0:
            self.estado = 'PARCIAL'
        else:
            self.estado = 'PENDIENTE'
        
        DocumentoFirmado.objects.filter(pk=self.pk).update(estado=self.estado)
    
    def verificar_integridad(self):
        """
        Verifica que el documento no ha sido modificado desde que se firmó.
        Retorna True si el hash actual coincide con el hash almacenado.
        """
        hash_actual = self.calcular_hash_documento()
        return hash_actual == self.hash_documento_original


class FirmaRequerida(models.Model):
    """
    Define los firmantes requeridos para un documento.
    Workflow de aprobación: Especifica quién debe firmar y en qué orden.
    """
    documento_firmado = models.ForeignKey(
        DocumentoFirmado,
        on_delete=models.CASCADE,
        related_name='firmas_requeridas',
        verbose_name="Documento"
    )
    
    firmante = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='documentos_por_firmar',
        verbose_name="Firmante Requerido"
    )
    
    # Orden de firma (para workflows secuenciales)
    orden = models.IntegerField(
        default=1,
        help_text="Orden en que debe firmarse (1 = primero). 0 = sin orden específico"
    )
    
    # Rol o título del firmante en este documento
    rol = models.CharField(
        max_length=100,
        blank=True,
        help_text="Ej: 'Elaboró', 'Revisó', 'Aprobó', 'Autorizó'"
    )
    
    # Posición de la firma en el documento (coordenadas)
    posicion_x = models.FloatField(
        default=0,
        help_text="Posición X en el documento (porcentaje 0-100)"
    )
    posicion_y = models.FloatField(
        default=0,
        help_text="Posición Y en el documento (porcentaje 0-100)"
    )
    pagina = models.IntegerField(
        default=1,
        help_text="Número de página donde se estampará la firma"
    )
    
    # Tamaño de la firma
    ancho = models.FloatField(default=15, help_text="Ancho de la firma (% del ancho de página)")
    alto = models.FloatField(default=8, help_text="Alto de la firma (% del alto de página)")
    
    # Estado
    obligatoria = models.BooleanField(
        default=True,
        help_text="Si es obligatoria, el documento no se completa sin esta firma"
    )
    
    notificado = models.BooleanField(
        default=False,
        help_text="Si se ha notificado al firmante"
    )
    fecha_notificacion = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Firma Requerida"
        verbose_name_plural = "Firmas Requeridas"
        ordering = ['orden', 'firmante__last_name']
        unique_together = ['documento_firmado', 'firmante', 'rol']
    
    def __str__(self):
        rol_txt = f" ({self.rol})" if self.rol else ""
        return f"{self.firmante.get_full_name()}{rol_txt} - {self.documento_firmado.documento.codigo}"


class Firma(models.Model):
    """
    Registro de una firma electrónica aplicada a un documento.
    Contiene toda la información de trazabilidad y seguridad.
    """
    documento_firmado = models.ForeignKey(
        DocumentoFirmado,
        on_delete=models.CASCADE,
        related_name='firmas',
        verbose_name="Documento Firmado"
    )
    
    firma_requerida = models.OneToOneField(
        FirmaRequerida,
        on_delete=models.CASCADE,
        related_name='firma_aplicada',
        verbose_name="Firma Requerida",
        null=True,
        blank=True
    )
    
    firmante = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='firmas_realizadas',
        verbose_name="Firmante"
    )
    
    # Imagen de la firma utilizada (puede venir del perfil o ser nueva)
    imagen_firma = models.ImageField(
        upload_to=firma_documento_path,
        validators=[FileExtensionValidator(allowed_extensions=['png'])],
        help_text="Imagen PNG de la firma estampada",
        storage=minio_storage
    )
    
    # Posición de la firma en el documento
    posicion_x = models.FloatField(help_text="Coordenada X (porcentaje)")
    posicion_y = models.FloatField(help_text="Coordenada Y (porcentaje)")
    pagina = models.IntegerField(default=1, help_text="Número de página")
    
    # Tamaño de la firma
    ancho = models.FloatField(default=15)
    alto = models.FloatField(default=8)
    
    # Datos de trazabilidad y seguridad
    fecha_firma = models.DateTimeField(auto_now_add=True)
    ip_firmante = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Dirección IP desde donde se firmó"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="Navegador/dispositivo usado para firmar"
    )
    
    # Hash de la firma para verificación
    hash_firma = models.CharField(
        max_length=64,
        editable=False,
        help_text="Hash SHA-256 de la imagen de firma"
    )
    
    # Token único de verificación
    token_verificacion = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Token único para verificar la autenticidad de la firma"
    )
    
    # Estado de la firma
    firmado = models.BooleanField(default=True)
    rechazado = models.BooleanField(default=False)
    motivo_rechazo = models.TextField(blank=True)
    
    # Metadatos adicionales
    comentarios = models.TextField(blank=True, help_text="Comentarios del firmante")
    
    class Meta:
        verbose_name = "Firma"
        verbose_name_plural = "Firmas"
        ordering = ['-fecha_firma']
    
    def __str__(self):
        return f"Firma de {self.firmante.get_full_name()} - {self.documento_firmado}"
    
    def save(self, *args, **kwargs):
        # Calcular hash de la imagen de firma
        if self.imagen_firma and not self.hash_firma:
            self.imagen_firma.seek(0)
            img_data = self.imagen_firma.read()
            self.hash_firma = hashlib.sha256(img_data).hexdigest()
        
        super().save(*args, **kwargs)
        
        # Actualizar estado del documento firmado
        if self.documento_firmado:
            self.documento_firmado.actualizar_estado()
    
    def generar_certificado_autenticidad(self):
        """
        Genera un diccionario con los datos del certificado de autenticidad
        que puede ser usado para crear un QR o PDF de verificación
        """
        return {
            'token': str(self.token_verificacion),
            'documento': self.documento_firmado.documento.codigo,
            'firmante': self.firmante.get_full_name(),
            'fecha': self.fecha_firma.isoformat(),
            'hash_firma': self.hash_firma,
            'hash_documento': self.documento_firmado.hash_documento_original,
        }


class AuditoriaFirmas(models.Model):
    """
    Log de auditoría para todas las acciones relacionadas con firmas.
    Proporciona trazabilidad completa del sistema.
    """
    ACCIONES = (
        ('CREAR_PERFIL', 'Creación de Perfil de Firma'),
        ('ACTUALIZAR_PERFIL', 'Actualización de Perfil'),
        ('SOLICITAR_FIRMA', 'Solicitud de Firma'),
        ('FIRMAR', 'Documento Firmado'),
        ('RECHAZAR', 'Firma Rechazada'),
        ('VERIFICAR', 'Verificación de Firma'),
        ('GENERAR_PDF', 'Generación de PDF Firmado'),
    )
    
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    accion = models.CharField(max_length=50, choices=ACCIONES)
    
    documento_firmado = models.ForeignKey(
        DocumentoFirmado,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    firma = models.ForeignKey(
        Firma,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    fecha = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    detalles = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = "Auditoría de Firma"
        verbose_name_plural = "Auditorías de Firmas"
        ordering = ['-fecha']
    
    def __str__(self):
        return f"{self.get_accion_display()} - {self.usuario} - {self.fecha}"
