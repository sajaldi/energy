from django.db import models
from django.contrib.contenttypes.models import ContentType
from core.storage import MinIOStorage

minio_storage = MinIOStorage()


def plantilla_upload_path(instance, filename):
    return f'plantillas_word/{instance.content_type.app_label}/{instance.content_type.model}/{filename}'


class PlantillaWord(models.Model):
    """
    Almacena plantillas Word (.docx) diseñadas por el usuario.
    Cada plantilla se asocia a un modelo de Django a través de ContentType,
    y contiene marcadores Jinja2 {{ campo }} que se rellenan al exportar un registro.
    """
    nombre = models.CharField(max_length=150, help_text="Nombre descriptivo de la plantilla")
    descripcion = models.TextField(blank=True)

    # Asociación genérica al modelo de Django
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name="Modelo",
        help_text="Modelo de Django al que aplica esta plantilla"
    )

    archivo = models.FileField(
        upload_to=plantilla_upload_path,
        storage=minio_storage,
        verbose_name="Archivo Word (.docx)",
        help_text="Sube aquí la plantilla Word diseñada con marcadores {{ campo }}"
    )

    activa = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plantilla Word"
        verbose_name_plural = "Plantillas Word"
        ordering = ['content_type', 'nombre']

    def __str__(self):
        return f"{self.nombre} ({self.content_type.app_label}.{self.content_type.model})"
