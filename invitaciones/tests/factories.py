"""
factory_boy factories for the invitaciones app tests.

Provides:
- UserFactory         : django.contrib.auth User with realistic data
- PerfilUsuarioFactory: linked to UserFactory, exposes invitation_status
- InvitationTokenFactory: with traits for active / expired / used / invalid tokens
"""

import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from core.models import PerfilUsuario
from invitaciones.models import InvitationToken

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Creates a minimal, valid User.  is_active=False for pending-invitation users."""

    class Meta:
        model = User
        # skip_postgeneration_save avoids a double-save when password is hashed
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    password = factory.PostGenerationMethodCall("set_password", "TestPass1!")


class PerfilUsuarioFactory(factory.django.DjangoModelFactory):
    """Creates a PerfilUsuario tied to a UserFactory instance."""

    class Meta:
        model = PerfilUsuario
        # The post_save signal on User already creates a PerfilUsuario,
        # so we use get_or_create to avoid IntegrityError.
        django_get_or_create = ("usuario",)

    usuario = factory.SubFactory(UserFactory)
    invitation_status = "active"

    class Params:
        pending = factory.Trait(invitation_status="pending")


class InvitationTokenFactory(factory.django.DjangoModelFactory):
    """
    Creates an InvitationToken.

    Traits
    ------
    active  : status='active',  expires_at = now + 72 h  (default behaviour)
    expired : status='active',  expires_at = now - 1 h   (past expiry)
    used    : status='used',    expires_at = now + 72 h
    invalid : status='invalid', expires_at = now + 72 h
    """

    class Meta:
        model = InvitationToken

    user = factory.SubFactory(UserFactory)
    token = factory.Sequence(lambda n: f"test_token_{n:06d}_{'x' * 20}")
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=72))
    status = "active"

    class Params:
        # An active, non-expired token (same as default — explicit for clarity)
        active = factory.Trait(
            status="active",
            expires_at=factory.LazyFunction(
                lambda: timezone.now() + timedelta(hours=72)
            ),
        )

        # Token whose expiry has already passed (still status='active' in DB —
        # expired tokens are only cleaned up by the periodic task)
        expired = factory.Trait(
            status="active",
            expires_at=factory.LazyFunction(
                lambda: timezone.now() - timedelta(hours=1)
            ),
        )

        # Token already consumed by the user
        used = factory.Trait(
            status="used",
            expires_at=factory.LazyFunction(
                lambda: timezone.now() + timedelta(hours=72)
            ),
        )

        # Token explicitly invalidated (e.g. resend overwrote it)
        invalid = factory.Trait(
            status="invalid",
            expires_at=factory.LazyFunction(
                lambda: timezone.now() + timedelta(hours=72)
            ),
        )
