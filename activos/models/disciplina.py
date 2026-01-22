from django.db import models

class Disciplina(models.Model):
    """
    Modelo jerárquico para clasificar planos por especialidad técnica.
    """
    nombre = models.CharField(max_length=100, unique=True)
    padre = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='subdisciplinas',
        help_text="Disciplina de nivel superior"
    )
    descripcion = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def get_ruta_completa(self, separador=' → '):
        """
        Devuelve la ruta completa de la disciplina en la jerarquía.
        Ej: 'Arquitectura → Plantas'
        """
        path = [self.nombre]
        curr = self.padre
        while curr:
            path.append(curr.nombre)
            curr = curr.padre
        return separador.join(reversed(path))

    def __str__(self):
        return self.get_ruta_completa()

    class Meta:
        verbose_name = "Disciplina"
        verbose_name_plural = "Disciplinas"
        app_label = 'activos'
        ordering = ['nombre']
