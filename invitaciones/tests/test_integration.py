# invitaciones/tests/test_integration.py
#
# Integration tests for the invitaciones app.
# These tests exercise multiple components together and interact with Celery,
# the Django admin, and the database.
#
# Planned tests (tasks 5.3, 10.2):
#   - test_dispatch_invitation_email_task_enqueued_after_user_creation   (Req 3.1, 3.6)
#   - test_dispatch_task_sends_correct_webhook_payload                   (Req 3.1)
#   - test_dispatch_task_retries_on_failure                              (Req 3.6)
#   - test_admin_resend_invitation_action_calls_service                  (Req 7.1, 7.2)
#   - test_admin_resend_action_unavailable_for_active_users              (Req 7.4)
#   - test_cleanup_expired_tokens_removes_only_expired_non_used          (Req 8.2)
