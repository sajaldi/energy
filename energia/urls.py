from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
from django.views.static import serve
from core.views_proxy import media_proxy
from core.views import global_search
from core.views_nav import menu_config_view
from presupuestos.views_webhook import requisicion_webhook_update
from invitaciones.views import complete_registration
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
from django.conf import settings as django_settings


class PowerAutomatePasswordResetView(auth_views.PasswordResetView):
    """
    Override del PasswordResetView que despacha el correo de reset
    a través del webhook de Power Automate en lugar del backend de email estándar.
    """
    template_name = 'registration/password_reset_form.html'

    def form_valid(self, form):
        import logging
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.contrib.auth.tokens import default_token_generator
        import requests

        logger = logging.getLogger(__name__)
        User = get_user_model()
        email = form.cleaned_data['email']

        users = list(User.objects.filter(email__iexact=email, is_active=True))

        # Si el correo no existe, mostrar error en el formulario
        if not users:
            form.add_error('email', 'No existe ninguna cuenta activa con ese correo electrónico.')
            return self.form_invalid(form)

        for user in users:
            uid   = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            # Usar BASE_REGISTRATION_URL para evitar el host interno de Coolify/Docker
            base_url = getattr(django_settings, 'BASE_REGISTRATION_URL', '').rstrip('/')
            if not base_url:
                base_url = self.request.build_absolute_uri('/').rstrip('/')
            reset_url = f"{base_url}/admin/reset/{uid}/{token}/"

            webhook_url = (
                getattr(django_settings, 'POWER_AUTOMATE_WEBHOOK_URL', '') or
                getattr(django_settings, 'POWER_AUTOMATE_INVITATION', '')
            )

            if webhook_url:
                payload = {
                    'email':           user.email,
                    'username':        user.get_full_name() or user.username,
                    'invitation_link': reset_url,
                    'tipo':            'password_reset',
                }
                try:
                    resp = requests.post(webhook_url, json=payload, timeout=15)
                    resp.raise_for_status()
                    logger.info('Password reset enviado a %s via PA', user.email)
                except Exception as exc:
                    logger.error('Error enviando reset via PA: %s', exc)
                    form.add_error(None, f'Error al enviar el correo: {exc}')
                    return self.form_invalid(form)
            else:
                logger.warning('POWER_AUTOMATE_WEBHOOK_URL no configurado, usando email estándar')
                opts = {
                    'use_https': self.request.is_secure(),
                    'token_generator': default_token_generator,
                    'from_email': None,
                    'email_template_name': 'registration/password_reset_email.html',
                    'request': self.request,
                }
                form.save(**opts)

        from django.shortcuts import redirect
        return redirect(self.get_success_url())

from django.views.generic import TemplateView, RedirectView
from mantenimiento.views.asistencia import AsistenciaKioskView

urlpatterns = [
    # Override global search before Django admin intercepts it
    path('admin/global-search/', global_search, name='global_search'),
    # Password reset flow (Fiori style — envío via Power Automate)
    # NOTA: estas vistas deben ir ANTES de path('admin/') para que no requieran login
    path('admin/password_reset/',         PowerAutomatePasswordResetView.as_view(success_url='/admin/password_reset/done/'), name='admin_password_reset'),
    path('admin/password_reset/done/',    auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),     name='password_reset_done'),
    path('admin/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(success_url='/admin/reset/done/', template_name='registration/password_reset_confirm.html'),  name='password_reset_confirm'),
    path('admin/reset/done/',             auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
    # La ruta del admin oficial de Django (debe ir DESPUÉS de las rutas de reset)
    path('admin/menu-config/', menu_config_view, name='menu_config'),
    path('admin/', admin.site.urls),
    # Proxy de medios para MinIO (Solución a Mixed Content)
    path('media-proxy/<path:path>', media_proxy, name='media_proxy'),
       # Incluye TODAS las URLs de tu app 'core' en la raíz del sitio.
    path('', include('core.urls', namespace='core')),
    path('activos/', include('activos.urls', namespace='activos')),
    path('mantenimiento/', include('mantenimiento.urls', namespace='mantenimiento')),
    path('portalsub/', include('portalsub.urls', namespace='portalsub')),
    # Sistema de firmas electrónicas
    path('firmas/', include('documentos.urls_firmas', namespace='firmas')),
    # Gestión Documental y Firmas
    path('documentos/', include('documentos.urls', namespace='documentos')),
    # Sistema de comunicaciones (Transmittals)
    path('comunicaciones/', include('comunicaciones.urls', namespace='comunicaciones')),
    path('proyectos/', include('proyectos.urls', namespace='proyectos')),
    path('presupuestos/', include('presupuestos.urls', namespace='presupuestos')),
    path('inventarios/', include('inventarios.urls', namespace='inventarios')),
    path('auditorias/', include('auditorias.urls', namespace='auditorias')),
    path('almacen/', include('almacen.urls', namespace='almacen')),
    path('seguridad/', include('seguridad.urls', namespace='seguridad')),
    path('callcenter/', include('callcenter.urls', namespace='callcenter')),
    path('servicios/', include('servicios.urls', namespace='servicios')),
    path('webhook/desde-power-automate/', requisicion_webhook_update, name='webhook_desde_power_automate'),
    path('webhook/desde-power-automate', requisicion_webhook_update),
    path('ayuda/', include('ayuda.urls', namespace='ayuda')),
    path('plantillas/', include('plantillas.urls', namespace='plantillas')),
    path('iot/', include('iot.urls', namespace='iot')),
    path('costos/', include('costos.urls', namespace='costos')),
    path('courses/', include('courses.urls', namespace='courses')),
    path('invitaciones/', include('invitaciones.urls', namespace='invitaciones')),
    path('notificaciones/', include('notificaciones.urls', namespace='notificaciones')),
    # complete-registration en la raíz (el link del correo apunta a esta URL)
    path('complete-registration', __import__('invitaciones.views', fromlist=['complete_registration']).complete_registration, name='complete_registration'),

    # Password reset flow ya definido arriba (antes del admin/)

    path('webpush/', include('webpush.urls')),
    
    # App Exclusiva de Asistencia (Kiosko)
    path('asistencia/', AsistenciaKioskView.as_view(), name='asistencia_kiosk_app'),
    # PWA Support - Servidos como plantillas para asegurar carga desde la raíz
    path('manifest.json', TemplateView.as_view(template_name='core/manifest.json', content_type='application/json')),
    path('sw.js', TemplateView.as_view(template_name='core/sw.js', content_type='application/javascript')),
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # En producción (Coolify/Docker), necesitamos servir archivos media explícitamente
    # si no estamos usando un servidor web externo (Nginx) para ello.
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
        re_path(r'^static/(?P<path>.*)$', serve, {
            'document_root': settings.STATIC_ROOT,
        }),
    ]
