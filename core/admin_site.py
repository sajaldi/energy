from django.contrib import admin
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.urls import reverse


class SoftComAdminSite(admin.AdminSite):
    """
    Sitio admin que después del login redirige a la página de inicio
    personalizable por perfil (core:home) en lugar del índice del admin.
    Preserva los deep-links (?next= apuntando a una página distinta del índice).
    """

    def login(self, request, extra_context=None):
        # El form de login (Jazzmin) conserva el ?next= en su action (app_path),
        # de modo que entrar por /admin/ (o por el botón "Admin") termina en
        # /admin/ tras autenticarse. Si el destino es el índice del admin o no
        # hay next, forzamos core:home. Los deep-links se respetan.
        context = dict(extra_context or {})
        admin_index = reverse("admin:index", current_app=self.name)
        next_value = request.POST.get(REDIRECT_FIELD_NAME) or request.GET.get(REDIRECT_FIELD_NAME)
        if not next_value or next_value == admin_index:
            context[REDIRECT_FIELD_NAME] = reverse("core:home")
            if REDIRECT_FIELD_NAME not in request.POST:
                q = request.GET.copy()
                q[REDIRECT_FIELD_NAME] = reverse("core:home")
                request.GET = q
        return super().login(request, extra_context=context)
