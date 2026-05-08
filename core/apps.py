from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Provisión y Gestión'

    def ready(self):
        from .signals_dynamics import register_dynamics_signals
        register_dynamics_signals()
