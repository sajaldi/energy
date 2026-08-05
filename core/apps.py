from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Provisión y Gestión'

    def ready(self):
        from .signals_dynamics import register_dynamics_signals
        register_dynamics_signals()
        self._install_admin_site()

    @staticmethod
    def _install_admin_site():
        """
        Reemplaza el sitio admin por SoftComAdminSite (que redirige el login al
        Inicio). django.contrib.admin.site es un LazyObject (DefaultAdminSite);
        se sustituye su instancia interna (_wrapped). Se ejecuta en ready() de
        'core', que en INSTALLED_APPS está ANTES de django.contrib.admin, de modo
        que el autodiscover registra todos los modelos en la instancia
        personalizada. Se re-registran los modelos ya registrados hasta el
        momento (p. ej. los de la propia 'core').
        """
        from django.contrib.admin import sites as admin_sites
        from core.admin_site import SoftComAdminSite

        current = admin_sites.site.__dict__.get("_wrapped")
        if isinstance(current, SoftComAdminSite):
            return

        new_site = SoftComAdminSite(name="admin")
        old_registry = getattr(admin_sites.site, "_registry", {})
        for model, model_admin in list(old_registry.items()):
            new_site.register(model, type(model_admin))

        admin_sites.site.__dict__["_wrapped"] = new_site
