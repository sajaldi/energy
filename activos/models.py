from django.db import models
from django.contrib.auth.models import User

class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

from mptt.models import MPTTModel, TreeForeignKey

class Ubicacion(MPTTModel):
    nombre = models.CharField(max_length=100)
    padre = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_ubicaciones')
    descripcion = models.TextField(blank=True, null=True)

    class MPTTMeta:
        order_insertion_by = ['nombre']
        parent_attr = 'padre'

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"

class Activo(models.Model):
    ESTADO_CHOICES = [
        ('OPERATIVO', 'Operativo'),
        ('MANTENIMIENTO', 'En Mantenimiento'),
        ('REPARACION', 'En Reparación'),
        ('OBSOLETO', 'Obsoleto/De Baja'),
    ]

    nombre = models.CharField(max_length=200, help_text="Nombre del activo o equipo")
    codigo_interno = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="Código de inventario interno")
    serie = models.CharField(max_length=100, blank=True, null=True, help_text="Número de serie del fabricante")
    
    marca = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name='activos')
    
    descripcion = models.TextField(blank=True, null=True)
    
    fecha_compra = models.DateField(blank=True, null=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='OPERATIVO')
    
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='activos_asignados', help_text="Persona responsable del activo")
    
    ubicacion_legacy = models.CharField(max_length=255, blank=True, null=True, help_text="Ubicación física del activo (Texto libre - Deprecado)")
    ubicacion = models.ForeignKey('Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='activos', help_text="Ubicación jerárquica")
    
    foto = models.ImageField(upload_to='activos_fotos/', blank=True, null=True)
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} ({self.codigo_interno or 'S/C'})"

    class Meta:
        verbose_name = "Activo"
        verbose_name_plural = "Activos"
