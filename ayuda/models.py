from django.db import models
from django.utils.text import slugify

class CategoriaAyuda(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    icono = models.CharField(max_length=50, default="fas fa-question-circle", help_text="Clase de FontAwesome (ej. fas fa-warehouse)")
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Categoría de Ayuda"
        verbose_name_plural = "Categorías de Ayuda"
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre

class ArticuloAyuda(models.Model):
    categoria = models.ForeignKey(CategoriaAyuda, on_delete=models.CASCADE, related_name="articulos")
    titulo = models.CharField(max_length=200)
    slug = models.SlugField(max_length=250, unique=True, blank=True)
    contenido = models.TextField(help_text="Contenido en formato Markdown")
    video_url = models.URLField(blank=True, null=True, help_text="URL opcional de video (YouTube/Vimeo)")
    
    # Contexto para Admin
    app_label = models.CharField(max_length=100, blank=True, help_text="App label del admin (ej. callcenter)")
    model_name = models.CharField(max_length=100, blank=True, help_text="Nombre del modelo (ej. solicitudticket)")
    es_contextual = models.BooleanField(default=False, help_text="Priorizar este artículo cuando se navega en el modelo indicado")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Artículo de Ayuda"
        verbose_name_plural = "Artículos de Ayuda"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.titulo)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.titulo
