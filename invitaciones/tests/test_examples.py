# invitaciones/tests/test_examples.py
#
# Example-based (unit) tests for the invitaciones app.
# Each test verifies a specific, concrete scenario described in requirements.md.
#
# Planned tests (tasks 1.2, 7.8):
#   - test_is_valid_returns_true_for_active_non_expired_token   (Req 2.2, 5.1)
#   - test_is_valid_returns_false_for_expired_token              (Req 2.2)
#   - test_is_valid_returns_false_for_used_token                 (Req 5.1)
#   - test_complete_registration_redirects_to_login              (Req 6.8)
#   - test_invalid_token_renders_invalid_page                    (Req 5.2)
#   - test_expired_token_renders_expired_page                    (Req 5.3)
#   - test_used_token_renders_used_page                          (Req 5.4)
#   - test_pa_dispatch_called_with_correct_payload               (Req 3.1)

import pytest
from unittest.mock import MagicMock, patch

from invitaciones.exceptions import PowerAutomateDispatchError
from invitaciones.services import PowerAutomateInvitationService


# ---------------------------------------------------------------------------
# PowerAutomateInvitationService tests  (Requirements 3.1, 3.7, 3.8)
# ---------------------------------------------------------------------------

class TestPowerAutomateInvitationService:
    """Unit tests for PowerAutomateInvitationService.dispatch()."""

    VALID_EMAIL = "usuario@example.com"
    VALID_USERNAME = "testuser"
    VALID_LINK = "https://app.example.com/complete-registration?token=abc123"
    VALID_WEBHOOK = "https://webhook.example.com/pa/trigger"

    def _make_service(self):
        return PowerAutomateInvitationService()

    # --- Req 3.1: payload correcto enviado al webhook -----------------------

    @pytest.mark.django_db
    def test_dispatch_sends_correct_payload(self, settings):
        """Req 3.1: el payload enviado contiene email, username e invitation_link."""
        settings.POWER_AUTOMATE_WEBHOOK_URL = self.VALID_WEBHOOK
        settings.INVITATION_SENDER_EMAIL = None

        with patch("invitaciones.services.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            self._make_service().dispatch(
                email=self.VALID_EMAIL,
                username=self.VALID_USERNAME,
                invitation_link=self.VALID_LINK,
            )

        mock_post.assert_called_once()
        _args, kwargs = mock_post.call_args
        assert kwargs["json"]["email"] == self.VALID_EMAIL
        assert kwargs["json"]["username"] == self.VALID_USERNAME
        assert kwargs["json"]["invitation_link"] == self.VALID_LINK
        assert "sender_email" not in kwargs["json"]

    # --- Req 3.7: sender_email opcional -------------------------------------

    @pytest.mark.django_db
    def test_dispatch_includes_sender_email_when_configured(self, settings):
        """Req 3.7: sender_email se incluye en el payload cuando está configurado."""
        settings.POWER_AUTOMATE_WEBHOOK_URL = self.VALID_WEBHOOK
        settings.INVITATION_SENDER_EMAIL = "noreply@empresa.com"

        with patch("invitaciones.services.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            self._make_service().dispatch(
                email=self.VALID_EMAIL,
                username=self.VALID_USERNAME,
                invitation_link=self.VALID_LINK,
            )

        _args, kwargs = mock_post.call_args
        assert kwargs["json"]["sender_email"] == "noreply@empresa.com"

    # --- Req 3.7: webhook URL no configurado --------------------------------

    @pytest.mark.django_db
    def test_dispatch_raises_if_webhook_url_not_configured(self, settings):
        """Req 3.7: lanza PowerAutomateDispatchError si POWER_AUTOMATE_WEBHOOK_URL está vacío."""
        settings.POWER_AUTOMATE_WEBHOOK_URL = ""

        service = self._make_service()
        with pytest.raises(PowerAutomateDispatchError, match="POWER_AUTOMATE_WEBHOOK_URL"):
            service.dispatch(
                email=self.VALID_EMAIL,
                username=self.VALID_USERNAME,
                invitation_link=self.VALID_LINK,
            )

    @pytest.mark.django_db
    def test_dispatch_raises_if_webhook_url_missing(self, settings):
        """Req 3.7: lanza PowerAutomateDispatchError si POWER_AUTOMATE_WEBHOOK_URL no existe."""
        # Eliminar el atributo para simular configuración ausente.
        if hasattr(settings, "POWER_AUTOMATE_WEBHOOK_URL"):
            delattr(settings, "POWER_AUTOMATE_WEBHOOK_URL")

        service = self._make_service()
        with pytest.raises(PowerAutomateDispatchError, match="POWER_AUTOMATE_WEBHOOK_URL"):
            service.dispatch(
                email=self.VALID_EMAIL,
                username=self.VALID_USERNAME,
                invitation_link=self.VALID_LINK,
            )

    # --- Req 3.8: validación de parámetros de entrada -----------------------

    @pytest.mark.django_db
    def test_dispatch_raises_if_email_is_empty(self, settings):
        """Req 3.8: lanza PowerAutomateDispatchError si email está vacío."""
        settings.POWER_AUTOMATE_WEBHOOK_URL = self.VALID_WEBHOOK

        service = self._make_service()
        with pytest.raises(PowerAutomateDispatchError, match="email"):
            service.dispatch(email="", username=self.VALID_USERNAME, invitation_link=self.VALID_LINK)

    @pytest.mark.django_db
    def test_dispatch_raises_if_username_is_empty(self, settings):
        """Req 3.8: lanza PowerAutomateDispatchError si username está vacío."""
        settings.POWER_AUTOMATE_WEBHOOK_URL = self.VALID_WEBHOOK

        service = self._make_service()
        with pytest.raises(PowerAutomateDispatchError, match="username"):
            service.dispatch(email=self.VALID_EMAIL, username="", invitation_link=self.VALID_LINK)

    @pytest.mark.django_db
    def test_dispatch_raises_if_invitation_link_is_empty(self, settings):
        """Req 3.8: lanza PowerAutomateDispatchError si invitation_link está vacío."""
        settings.POWER_AUTOMATE_WEBHOOK_URL = self.VALID_WEBHOOK

        service = self._make_service()
        with pytest.raises(PowerAutomateDispatchError, match="invitation_link"):
            service.dispatch(email=self.VALID_EMAIL, username=self.VALID_USERNAME, invitation_link="")

    # --- HTTP failure raises PowerAutomateDispatchError ---------------------

    @pytest.mark.django_db
    def test_dispatch_raises_on_http_error(self, settings):
        """Req 3.1: lanza PowerAutomateDispatchError si el webhook devuelve error HTTP."""
        import requests as req_lib
        settings.POWER_AUTOMATE_WEBHOOK_URL = self.VALID_WEBHOOK
        settings.INVITATION_SENDER_EMAIL = None

        with patch("invitaciones.services.requests.post") as mock_post:
            mock_post.side_effect = req_lib.RequestException("Connection refused")

            service = self._make_service()
            with pytest.raises(PowerAutomateDispatchError, match="webhook"):
                service.dispatch(
                    email=self.VALID_EMAIL,
                    username=self.VALID_USERNAME,
                    invitation_link=self.VALID_LINK,
                )
