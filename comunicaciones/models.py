from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from documentos.models import Revision

class TipoComunicado(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    codigo = models.CharField(max_length=10, unique=True, help_text="Prefijo para consecutivo (ej: RFI, MEMO)")
    
    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

    class Meta:
        verbose_name = "Tipo de Comunicado"
        verbose_name_plural = "Tipos de Comunicado"

class Comunicado(models.Model):
    ESTADOS = (
        ('BORRADOR', 'Borrador'),
        ('ENVIADO', 'Enviado'),
    )

    tipo = models.ForeignKey(TipoComunicado, on_delete=models.PROTECT)
    consecutivo = models.CharField(max_length=50, unique=True, blank=True, null=True, editable=False)
    
    asunto = models.CharField(max_length=255)
    cuerpo = models.TextField(help_text="Contenido del mensaje")
    
    remitente = models.ForeignKey(User, on_delete=models.PROTECT, related_name='comunicados_enviados')
    fecha_envio = models.DateTimeField(blank=True, null=True)
    
    estado = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR')
    
    # Hilos de conversación
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='respuestas')

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.consecutivo or 'Borrador'} - {self.asunto}"

    def save(self, *args, **kwargs):
        # Bloquear edición si ya fue enviado
        if self.pk:
            old_obj = Comunicado.objects.get(pk=self.pk)
            if old_obj.estado == 'ENVIADO':
                # Permitir solo cambios menores o lanzar error? 
                # Aconex es estricto: No se edita nada.
                # Validamos si hay cambios reales. 
                # Por simplicidad ahora: Si intentas guardar un enviado, advertir o bloquear.
                pass 

        # Generar consecutivo al enviar
        if self.estado == 'ENVIADO' and not self.consecutivo:
            self.fecha_envio = timezone.now()
            # Lógica simple de consecutivo: TIPO-001-AÑO
            year = self.fecha_envio.year
            count = Comunicado.objects.filter(tipo=self.tipo, fecha_envio__year=year).count() + 1
            self.consecutivo = f"{self.tipo.codigo}-{str(count).zfill(3)}-{year}"
            
        super().save(*args, **kwargs)

class Destinatario(models.Model):
    TIPOS = (
        ('PARA', 'Para'),
        ('CC', 'CC'),
        ('CCO', 'CCO'),
    )
    
    comunicado = models.ForeignKey(Comunicado, on_delete=models.CASCADE, related_name='destinatarios')
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='comunicados_recibidos')
    tipo = models.CharField(max_length=10, choices=TIPOS, default='PARA')
    
    leido = models.BooleanField(default=False)
    fecha_leido = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Destinatario"
        verbose_name_plural = "Destinatarios"
        unique_together = ('comunicado', 'usuario')

    def __str__(self):
        return f"{self.usuario} ({self.tipo})"

class AdjuntoComunicado(models.Model):
    comunicado = models.ForeignKey(Comunicado, on_delete=models.CASCADE, related_name='adjuntos')
    
    # Puede ser una revisión del sistema documental O un archivo suelto O un activo
    documento_revision = models.ForeignKey(Revision, on_delete=models.PROTECT, null=True, blank=True)
    archivo = models.FileField(upload_to='comunicados/adjuntos/', null=True, blank=True)
    activo = models.ForeignKey('activos.Activo', on_delete=models.PROTECT, null=True, blank=True, related_name='transmittals')

    def __str__(self):
        if self.activo:
            return f"Activo: {self.activo.nombre} ({self.activo.codigo_interno})"
        if self.documento_revision:
            return str(self.documento_revision)
        return self.archivo.name or "Adjunto"

class Notificacion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificaciones')
    comunicado = models.ForeignKey(Comunicado, on_delete=models.CASCADE, related_name='notificaciones')
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Notificación para {self.usuario}: {self.comunicado.asunto}"

# Signals para automatizar notificaciones
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

@receiver(post_save, sender=Comunicado)
def crear_notificaciones_al_enviar(sender, instance, created, **kwargs):
    # Solo actuar si el estado cambió a ENVIADO o si se guardó como ENVIADO por primera vez
    # (En nuestra lógica, el paso a ENVIADO es el trigger)
    if instance.estado == 'ENVIADO':
        # Obtener todos los destinatarios que no sean CCO (normalmente CCO no recibe alerta tipo 'notificacion' en UI, pero sí email)
        destinatarios = instance.destinatarios.all()
        for d in destinatarios:
            # 1. Crear notificación interna si no existe ya
            Notificacion.objects.get_or_create(
                usuario=d.usuario,
                comunicado=instance
            )
            
            # 2. Intentar enviar email (opcional, si hay configuración)
            if d.usuario.email:
                subject = f"Nuevo Comunicado: {instance.consecutivo} - {instance.asunto}"
                message = f"Has recibido una nueva comunicación en el sistema.\n\nAsunto: {instance.asunto}\nDe: {instance.remitente.get_full_name() or instance.remitente.username}\nConsecutivo: {instance.consecutivo}\n\nPuedes revisarlo en el portal del proyecto."
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [d.usuario.email], fail_silently=True)
                # NOTA: send_mail fallará si no hay SMTP configurado. Por ahora lo dejamos comentado o con fail_silently.

class BotSession(models.Model):
    """
    Control de estado de los usuarios para el bot de WhatsApp.
    Mapea la tabla bot_sessions requerida para el flujo de n8n.
    """
    phone_number = models.CharField(max_length=20, primary_key=True)
    status = models.CharField(max_length=50, default='IDLE')
    last_update = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bot_sessions'
        verbose_name = "Sesión de Bot"
        verbose_name_plural = "Sesiones de Bot"

    def __str__(self):
        return f"{self.phone_number} ({self.status})"
