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

    def get_ruta_completa(self, separador=' → '):
        """
        Devuelve la ruta completa de la ubicación en la jerarquía.
        Ej: 'Campus Principal → Edificio A → Nivel 1'
        
        Si la instancia no está guardada, devuelve solo el nombre.
        """
        # Verificar si la instancia está guardada en la BD
        if not self.pk:
            return self.nombre
        
        try:
            ancestros = self.get_ancestors(include_self=True)
            return separador.join([u.nombre for u in ancestros])
        except:
            # Fallback si hay algún problema
            return self.nombre
    
    def get_clave_unica(self):
        """
        Devuelve una clave única compuesta por la concatenación de toda la jerarquía.
        Ej: 'Campus Principal|Edificio A|Nivel 1'
        
        Esto permite tener múltiples ubicaciones con el mismo nombre en diferentes padres.
        Si la instancia no está guardada, devuelve solo el nombre.
        """
        # Verificar si la instancia está guardada en la BD
        if not self.pk:
            return self.nombre
        
        return self.get_ruta_completa(separador='|')
    
    @property
    def ruta_completa(self):
        """Propiedad para acceso rápido a la ruta completa"""
        return self.get_ruta_completa()

    def __str__(self):
        return self.get_ruta_completa()

    class Meta:
        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"

class Marca(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"

class Modelo(models.Model):
    nombre = models.CharField(max_length=100)
    marca = models.ForeignKey(Marca, on_delete=models.CASCADE, related_name='modelos')

    def __str__(self):
        return f"{self.marca} - {self.nombre}"

    class Meta:
        verbose_name = "Modelo"
        verbose_name_plural = "Modelos"

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
    
    marca_legacy = models.CharField(max_length=100, blank=True, null=True)
    modelo_legacy = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.ForeignKey(Modelo, on_delete=models.SET_NULL, null=True, blank=True, related_name='activos')
    
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
