"""
pytest / Hypothesis configuration for the invitaciones app test suite.

Registers and loads the "ci" Hypothesis profile so that all property-based
tests in this suite run with consistent settings without having to decorate
each test individually.

Fixtures
--------
pending_user                  : a User + PerfilUsuario in 'pending' status
pending_user_with_valid_token : pending_user accompanied by a valid active token
"""

import pytest
from django.contrib.auth import get_user_model
from hypothesis import HealthCheck, settings

from invitaciones.tests.factories import (
    InvitationTokenFactory,
    PerfilUsuarioFactory,
    UserFactory,
)

# ---------------------------------------------------------------------------
# Hypothesis profile
# ---------------------------------------------------------------------------

settings.register_profile(
    "ci",
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
)

settings.load_profile("ci")

# ---------------------------------------------------------------------------
# pytest-django fixtures
# ---------------------------------------------------------------------------

User = get_user_model()


@pytest.fixture
def pending_user(db):
    """
    Returns a (user, perfil) tuple.

    The user is inactive (is_active=False) and the associated PerfilUsuario
    has invitation_status='pending', simulating a freshly invited user who
    has not yet completed registration.
    """
    user = UserFactory(is_active=False)
    # The post_save signal creates a PerfilUsuario automatically; we just
    # update invitation_status to 'pending'.
    perfil = user.perfil
    perfil.invitation_status = "pending"
    perfil.save()
    return user, perfil


@pytest.fixture
def pending_user_with_valid_token(pending_user):
    """
    Returns a (user, perfil, token) tuple.

    Extends *pending_user* with a freshly generated active InvitationToken
    (expires 72 hours from now).
    """
    user, perfil = pending_user
    token = InvitationTokenFactory(user=user, active=True)
    return user, perfil, token
