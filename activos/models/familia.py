from django.db import models

class Familia(models.Model):
    nombre = models.CharField(max_length=100)
    padre = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfamilias')
    descripcion = models.TextField(blank=True, null=True)

    def get_ruta_completa(self, separador=' → '):
        """
        Devuelve la ruta completa de la familia en la jerarquía.
        Ej: 'Electricidad → Motores → Trifásicos'
        """
        path = [self.nombre]
        if not self.id:
            return self.nombre
            
        visited = {self.id}
        curr = self.padre
        while curr:
            if curr.id in visited:
                path.append(f"[BUCLE DETECTADO: {curr.nombre}]")
                break
            visited.add(curr.id)
            path.append(curr.nombre)
            curr = curr.padre
        return separador.join(reversed(path))

    def __str__(self):
        return self.get_ruta_completa()

    class Meta:
        verbose_name = "Familia"
        verbose_name_plural = "Familias"
        unique_together = ('nombre', 'padre')
        app_label = 'activos'
