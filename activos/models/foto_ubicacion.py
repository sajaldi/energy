from django.db import models
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from .ubicacion import Ubicacion
import os
from PIL import Image, ExifTags
from io import BytesIO

class FotoUbicacion(models.Model):
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.CASCADE, related_name='fotos')
    foto = models.ImageField(upload_to='ubicaciones/fotos/')
    descripcion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Descripción")
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Foto de Ubicación"
        verbose_name_plural = "Fotos de Ubicación"
        ordering = ['-creado_en']

    def __str__(self):
        return f"Foto {self.id} - {self.ubicacion.nombre}"

    def save(self, *args, **kwargs):
        """
        Sobrescribe el método save para optimizar la imagen antes de guardarla.
        - Corrige orientación EXIF.
        - Redimensiona a max 1600px manteniendo proporción.
        - Comprime a JPEG de alta calidad (85).
        """
        if self.foto and not self.pk: # Solo optimizar al crear (si es nueva)
            try:
                img = Image.open(self.foto)
                
                # 1. Corregir orientación basada en EXIF
                try:
                    for orientation in ExifTags.TAGS.keys():
                        if ExifTags.TAGS[orientation] == 'Orientation':
                            break
                    exif = dict(img._getexif().items())

                    if exif[orientation] == 3:
                        img = img.rotate(180, expand=True)
                    elif exif[orientation] == 6:
                        img = img.rotate(270, expand=True)
                    elif exif[orientation] == 8:
                        img = img.rotate(90, expand=True)
                except (AttributeError, KeyError, IndexError):
                    # No hay EXIF o no tiene orientación
                    pass

                # 2. Redimensionar si es muy grande (Max 1600px)
                max_size = (1600, 1600)
                if img.height > max_size[1] or img.width > max_size[0]:
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)

                # 3. Convertir a RGB si es necesario (para guardar como JPEG)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # 4. Guardar optimizada en un buffer
                output = BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                output.seek(0)

                # Cambiar el nombre del archivo si es necesario y asignar el nuevo contenido
                name = os.path.splitext(self.foto.name)[0] + '.jpg'
                self.foto = ContentFile(output.read(), name=name)
                
            except Exception as e:
                # Si algo falla en la optimización, guardar la original por seguridad
                print(f"Error optimizando imagen: {e}")
        
        super().save(*args, **kwargs)
