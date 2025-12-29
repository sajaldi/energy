from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # La ruta del admin oficial de Django
    path('admin/', admin.site.urls),
       # Incluye TODAS las URLs de tu app 'core' en la raíz del sitio.
    path('', include('core.urls', namespace='core')),
    path('activos/', include('activos.urls', namespace='activos')),
    path('mantenimiento/', include('mantenimiento.urls', namespace='mantenimiento')),
    # Sistema de firmas electrónicas
    path('firmas/', include('documentos.urls_firmas', namespace='firmas')),
    # Sistema de comunicaciones (Transmittals)
    path('comunicaciones/', include('comunicaciones.urls', namespace='comunicaciones')),
    path('proyectos/', include('proyectos.urls', namespace='proyectos')),
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