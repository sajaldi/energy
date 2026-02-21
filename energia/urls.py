from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
from django.views.static import serve
from core.views_proxy import media_proxy

urlpatterns = [
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
    # PWA Support
    path('manifest.json', serve, {'document_root': settings.STATICFILES_DIRS[0], 'path': 'core/manifest.json'}),
    path('sw.js', serve, {'document_root': settings.STATICFILES_DIRS[0], 'path': 'core/sw.js'}),
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
