from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
import os

def compress_image(image_field, max_width=1024, quality=70):
    """
    Comprime y redimensiona una imagen para ahorrar espacio y mejorar tiempos de carga.
    Retorna un objeto InMemoryUploadedFile listo para ser asignado a un ImageField.
    """
    if not image_field:
        return image_field

    try:
        # Abrir la imagen usando Pillow
        img = Image.open(image_field)
        
        # Convertir a RGB si es necesario (ej: de RGBA/PNG a JPEG)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Redimensionar si es más ancha que el máximo permitido
        if img.width > max_width:
            new_height = int((max_width / img.width) * img.height)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        # Guardar en un buffer de memoria
        output = BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)
        
        # Generar nombre de archivo (asegurar extensión .jpg)
        original_name = os.path.basename(image_field.name)
        name_without_ext = os.path.splitext(original_name)[0]
        new_filename = f"{name_without_ext}.jpg"
        
        # Crear el objeto de archivo para Django
        return InMemoryUploadedFile(
            output, 
            'ImageField', 
            new_filename,
            'image/jpeg', 
            sys.getsizeof(output), 
            None
        )
    except Exception as e:
        print(f"[ERROR COMPRESS_IMAGE] {str(e)}")
        return image_field
