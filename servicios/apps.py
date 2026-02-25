from django.apps import AppConfig


class ServiciosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'servicios'

    def ready(self):
        try:
            import servicios.tasks
        except ImportError:
            pass
