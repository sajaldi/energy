from django.db import models
from django.contrib.auth.models import User


class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('INFO', 'Información'),
        ('SUCCESS', 'Éxito'),
        ('WARNING', 'Advertencia'),
        ('ERROR', 'Error'),
    ]
    MODULO_CHOICES = [
        ('MANTENIMIENTO', 'Mantenimiento'),
        ('PRESUPUESTOS', 'Presupuestos'),
        ('PORTAL_SUB', 'Portal Subcontratistas'),
        ('INVENTARIOS', 'Inventarios'),
        ('SISTEMA', 'Sistema'),
    ]
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='notificaciones_app',
        verbose_name='Usuario'
    )
    emisor = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='notificaciones_enviadas',
        verbose_name='Emisor'
    )
    titulo = models.CharField(max_length=200, verbose_name='Título')
    mensaje = models.TextField(verbose_name='Mensaje')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='INFO', verbose_name='Tipo')
    modulo = models.CharField(max_length=50, choices=MODULO_CHOICES, default='SISTEMA', verbose_name='Módulo', db_index=True)
    enlace = models.CharField(max_length=500, blank=True, verbose_name='Enlace')
    icono = models.CharField(max_length=50, blank=True, verbose_name='Ícono')
    leida = models.BooleanField(default=False, db_index=True, verbose_name='Leída')
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name='Creado')

    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['user', 'leida']),
            models.Index(fields=['user', 'modulo']),
        ]

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.titulo} - {self.user.username}"

    def marcar_como_leida(self):
        if not self.leida:
            self.leida = True
            self.save(update_fields=['leida'])

    @classmethod
    def no_leidas(cls, user):
        return cls.objects.filter(user=user, leida=False)

    @classmethod
    def conteo_no_leidas(cls, user):
        return cls.no_leidas(user).count()
