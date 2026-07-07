from django.conf import settings
from django.db import models
from django.utils import timezone


class InvitationToken(models.Model):
    STATUS_CHOICES = [
        ('active',  'Active'),
        ('used',    'Used'),
        ('expired', 'Expired'),
        ('invalid', 'Invalid'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='invitation_token',
    )
    token = models.CharField(max_length=128, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='active',
    )

    class Meta:
        verbose_name = 'Invitation Token'
        verbose_name_plural = 'Invitation Tokens'

    def __str__(self):
        return f"InvitationToken(user={self.user_id}, status={self.status})"

    def is_valid(self) -> bool:
        """True si el token está active y no ha expirado."""
        return self.status == 'active' and self.expires_at > timezone.now()
