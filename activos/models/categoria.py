from django.db import models

class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    padre = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategorias')
    icono = models.CharField(max_length=50, default='location', help_text="Nombre del icono de Ionicons (ej: flash, water, construct, bulb)")
    descripcion = models.TextField(blank=True, null=True)
    codigo_exoneracion = models.ForeignKey(
        'presupuestos.CodigoExoneracion',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='categorias_activos',
        verbose_name="Código de exoneración",
        help_text="Código arancelario de exoneración fiscal vinculado a esta categoría"
    )

    @property
    def tiene_hijos(self):
        """Devuelve True si tiene sub-categorías o hay activos asociados a esta categoría."""
        # Importación tardía para evitar círculos
        from .activo import Activo
        return self.subcategorias.exists() or Activo.objects.filter(modelo__categoria=self).exists()

    def get_descendants(self, include_self=True):
        """
        Retorna un QuerySet con todos los descendientes de esta categoría.
        """
        descendants_ids = []
        if include_self:
            descendants_ids.append(self.id)
        
        def _get_children(parent):
            for child in parent.subcategorias.all():
                descendants_ids.append(child.id)
                _get_children(child)
        
        _get_children(self)
        return Categoria.objects.filter(id__in=descendants_ids)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        app_label = 'activos'
