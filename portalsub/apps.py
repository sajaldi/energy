from django.apps import AppConfig


class PortalsubConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'portalsub'
    verbose_name = 'Portal Subcontratistas'

    def ready(self):
        import portalsub.signals  # noqa
