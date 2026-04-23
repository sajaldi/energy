from django.apps import AppConfig


class MantenimientoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mantenimiento'

    def ready(self):
        import mantenimiento.signals

