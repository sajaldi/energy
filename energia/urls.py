from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
from django.views.static import serve
from core.views_proxy import media_proxy
from core.views import global_search
from presupuestos.views_webhook import requisicion_webhook_update

from django.views.generic import TemplateView, RedirectView
from mantenimiento.views.asistencia import AsistenciaKioskView

urlpatterns = [
    # Override global search before Django admin intercepts it
    path('admin/global-search/', global_search, name='global_search'),
    # La ruta del admin oficial de Django
    path('admin/', admin.site.urls),
    # Proxy de medios para MinIO (Solución a Mixed Content)
    path('media-proxy/<path:path>', media_proxy, name='media_proxy'),
       # Incluye TODAS las URLs de tu app 'core' en la raíz del sitio.
    path('', include('core.urls', namespace='core')),
    path('activos/', include('activos.urls', namespace='activos')),
    path('mantenimiento/', include('mantenimiento.urls', namespace='mantenimiento')),
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
