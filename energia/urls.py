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
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)