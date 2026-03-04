from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class DocumentoAltaBaja(models.Model):
    """
    Documento oficial de Alta o Baja de activos.
    Agrupa un listado de activos que se dan de alta o baja.
    """
    TIPOS = (
        ('ALTA', 'Alta'),
        ('BAJA', 'Baja'),
    )

    ESTADOS = (
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE', 'Pendiente de Aprobación'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
    )

    tipo = models.CharField(max_length=10, choices=TIPOS, verbose_name="Tipo de Documento")
    numero = models.CharField(max_length=50, unique=True, blank=True, verbose_name="Número de Documento", help_text="Se genera automáticamente")
    fecha = models.DateField(default=timezone.now, verbose_name="Fecha del Documento")
    motivo = models.TextField(verbose_name="Motivo / Justificación")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR')
    observaciones = models.TextField(blank=True, verbose_name="Observaciones Adicionales")

    # Responsables
    elaborado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='docs_altabaja_elaborados',
        verbose_name="Elaborado por"
    )
    autorizado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='docs_altabaja_autorizados',
        verbose_name="Autorizado por"
    )
    recibido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='docs_altabaja_recibidos',
        verbose_name="Recibido por"
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.numero:
            from datetime import datetime
            anio = datetime.now().year
            prefix = f"{self.tipo}-"
            suffix = f"-{anio}"

            last = DocumentoAltaBaja.objects.filter(
                numero__startswith=prefix,
                numero__endswith=suffix
            ).order_by('numero').last()

            if last:
                try:
                    num_str = last.numero.replace(prefix, '').replace(suffix, '')
                    new_num = int(num_str) + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1

            self.numero = f"{prefix}{str(new_num).zfill(5)}{suffix}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.numero} ({self.fecha})"

    @property
    def total_activos(self):
        return self.items.count()

    class Meta:
        verbose_name = "Documento de Alta/Baja"
        verbose_name_plural = "Documentos de Alta/Baja"
        ordering = ['-fecha']
        app_label = 'activos'


class ItemAltaBaja(models.Model):
    """
    Ítem individual dentro de un documento de Alta/Baja.
    """
    documento = models.ForeignKey(
        DocumentoAltaBaja,
        on_delete=models.CASCADE,
        related_name='items'
    )
    activo = models.ForeignKey(
        'activos.Activo',
        on_delete=models.CASCADE,
        related_name='documentos_altabaja'
    )
    observacion = models.CharField(max_length=500, blank=True, help_text="Observación específica para este activo")

    def __str__(self):
        return f"{self.documento.get_tipo_display()} - {self.activo.nombre}"

    class Meta:
        verbose_name = "Activo en Documento"
        verbose_name_plural = "Activos en Documento"
        unique_together = ('documento', 'activo')
        app_label = 'activos'


def altabaja_upload_path(instance, filename):
    """Organiza archivos por documento: altabaja/<numero>/<filename>"""
    numero = instance.documento.numero or 'sin_numero'
    return f'altabaja/{numero}/{filename}'


class ArchivoAltaBaja(models.Model):
    """
    Archivo adjunto a un Documento de Alta/Baja.
    Puede ser imagen, PDF, o cualquier tipo de archivo.
    """
    documento = models.ForeignKey(
        DocumentoAltaBaja,
        on_delete=models.CASCADE,
        related_name='archivos'
    )
    archivo = models.FileField(upload_to=altabaja_upload_path, verbose_name="Archivo")
    comentario = models.CharField(max_length=500, blank=True, verbose_name="Comentario")
    subido_en = models.DateTimeField(auto_now_add=True)

    @property
    def es_imagen(self):
        if self.archivo:
            ext = self.archivo.name.lower()
            return any(ext.endswith(e) for e in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'])
        return False

    @property
    def nombre_archivo(self):
        if self.archivo:
            return self.archivo.name.split('/')[-1]
        return ""

    def __str__(self):
        return f"{self.nombre_archivo} - {self.documento.numero}"

    class Meta:
        verbose_name = "Archivo Adjunto"
        verbose_name_plural = "Archivos Adjuntos"
        ordering = ['subido_en']
        app_label = 'activos'
