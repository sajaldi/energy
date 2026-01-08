from django.db import models

class Ubicacion(models.Model):
    TIPO_CHOICES = [
        ('EDIFICIO', 'Edificio'),
        ('NIVEL', 'Nivel/Piso'),
        ('ESPACIO', 'Espacio/Área'),
        ('OTRO', 'Otro'),
    ]
    
    nombre = models.CharField(max_length=100)
    padre = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_ubicaciones')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='NIVEL', help_text="Tipo de ubicación")
    descripcion = models.TextField(blank=True, null=True)
    orden = models.PositiveIntegerField(default=0, help_text="Orden de visualización y programación")

    def get_ruta_completa(self, separador=' → '):
        """
        Devuelve la ruta completa de la ubicación en la jerarquía.
        Ej: 'Campus Principal → Edificio A → Nivel 1'
        """
        path = [self.nombre]
        curr = self.padre
        while curr:
            path.append(curr.nombre)
            curr = curr.padre
        return separador.join(reversed(path))
    
    def get_clave_unica(self):
        """Devuelve una clave única compuesta por la concatenación de toda la jerarquía."""
        return self.get_ruta_completa(separador='|')
    
    @property
    def ruta_completa(self):
        """Propiedad para acceso rápido a la ruta completa"""
        return self.get_ruta_completa()
    
    @property
    def level(self):
        """Calcula el nivel de profundidad (0 para raíz)."""
        count = 0
        curr = self.padre
        while curr:
            count += 1
            curr = curr.padre
        return count

    def get_root(self):
        """Devuelve el nodo raíz de la jerarquía (Campus/Sede)."""
        curr = self
        while curr.padre:
            curr = curr.padre
        return curr

    def get_descendants(self, include_self=True):
        """
        Reemplazo manual para get_descendants de MPTT.
        Retorna un QuerySet con todos los descendientes.
        """
        descendants_ids = []
        if include_self:
            descendants_ids.append(self.id)
        
        def _get_children(parent):
            for child in parent.sub_ubicaciones.all():
                descendants_ids.append(child.id)
                _get_children(child)
        
        _get_children(self)
        return Ubicacion.objects.filter(id__in=descendants_ids)

    def __str__(self):
        return self.get_ruta_completa()

    class Meta:
        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"
        unique_together = ('nombre', 'padre')
        app_label = 'activos'
