from django.contrib import admin
from django.db import models
from .models import Ubicacion

class ActivoFaltantesFilter(admin.SimpleListFilter):
    title = 'Calidad de Datos'
    parameter_name = 'faltante'

    def lookups(self, request, model_admin):
        return (
            ('serie', '❌ Sin N° Serie'),
            ('responsable', '👤 Sin Responsable'),
            ('ubicacion', '📍 Sin Ubicación'),
            ('codigo', '🆔 Sin Código Interno'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'serie':
            return queryset.filter(models.Q(serie__isnull=True) | models.Q(serie=''))
        if self.value() == 'responsable':
            return queryset.filter(responsable__isnull=True)
        if self.value() == 'ubicacion':
            return queryset.filter(ubicacion__isnull=True)
        if self.value() == 'codigo':
            return queryset.filter(models.Q(codigo_interno__isnull=True) | models.Q(codigo_interno=''))
        return queryset

class UbicacionHierarchyFilter(admin.SimpleListFilter):
    title = 'Ubicación'
    parameter_name = 'ubicacion_id'

    def lookups(self, request, model_admin):
        # Optimización: No cargar miles de ubicaciones con ruta_completa en el sidebar.
        # Solo mostrar las ubicaciones raíz o usar un límite razonable.
        lookups = [('none', '📍 Sin Ubicación Asignada')]
        
        # Solo mostramos los primeros niveles para evitar bloqueos por volumen
        locations = Ubicacion.objects.filter(padre__isnull=True).order_by('nombre')
        for loc in locations:
            lookups.append((loc.id, f"🏢 {loc.nombre}"))
            
        return lookups

    def queryset(self, request, queryset):
        val = self.value()
        if val:
            if val == 'none':
                return queryset.filter(ubicacion__isnull=True)
            
            try:
                ubicacion = Ubicacion.objects.get(id=val)
                # Obtener todos los descendientes incluyendo el actual
                descendientes_ids = ubicacion.get_descendants(include_self=True).values_list('id', flat=True)
                return queryset.filter(ubicacion_id__in=descendientes_ids)
            except (Ubicacion.DoesNotExist, ValueError):
                return queryset
        return queryset
