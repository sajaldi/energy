from django.db import models
from django.contrib.auth.models import User
from colorfield.fields import ColorField

class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    icono = models.CharField(max_length=50, default='location', help_text="Nombre del icono de Ionicons (ej: flash, water, construct, bulb)")
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"



class Ubicacion(models.Model):
    nombre = models.CharField(max_length=100)
    padre = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_ubicaciones')
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
    serie = models.CharField(max_length=100, blank=True, null=True, help_text="Número de serie del fabricante", db_index=True)
    
    marca_legacy = models.CharField(max_length=100, blank=True, null=True)
    modelo_legacy = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.ForeignKey(Modelo, on_delete=models.SET_NULL, null=True, blank=True, related_name='activos')
    
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name='activos')
    
    descripcion = models.TextField(blank=True, null=True)
    
    fecha_compra = models.DateField(blank=True, null=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='OPERATIVO', db_index=True)
    
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='activos_asignados', help_text="Persona responsable del activo")
    
    ubicacion_legacy = models.CharField(max_length=255, blank=True, null=True, help_text="Ubicación física del activo (Texto libre - Deprecado)")
    ubicacion = models.ForeignKey('Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='activos', help_text="Ubicación jerárquica")
    
    foto = models.ImageField(upload_to='activos_fotos/', blank=True, null=True)
    
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} ({self.codigo_interno or 'S/C'})"

    class Meta:
        verbose_name = "Activo"
        verbose_name_plural = "Activos"

class Plano(models.Model):
    nombre = models.CharField(max_length=100)
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.CASCADE, related_name='planos')
    activos = models.ManyToManyField('Activo', blank=True, related_name='planos', help_text="Activos que se visualizan en este plano")
    archivo = models.FileField(upload_to='planos/', null=True, blank=True, help_text="Subir imagen o PDF del plano")
    descripcion = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} - {self.ubicacion.nombre}"
        
    class Meta:
        verbose_name = "Plano"
        verbose_name_plural = "Planos"

class VisorPlano(models.Model):
    nombre = models.CharField(max_length=100)
    plano = models.ForeignKey(Plano, on_delete=models.CASCADE, related_name='visores')
    descripcion = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.plano.nombre})"

    class Meta:
        verbose_name = "Visor de Plano"
        verbose_name_plural = "Visores de Planos"

class PinPlano(models.Model):
    visor = models.ForeignKey(VisorPlano, on_delete=models.CASCADE, related_name='pines')
    activo = models.ForeignKey(Activo, on_delete=models.CASCADE, related_name='pines_planos', null=True, blank=True)
    x = models.FloatField(help_text="Posición X en píxeles absolutos")
    y = models.FloatField(help_text="Posición Y en píxeles absolutos")
    color = ColorField(default='#FF0000')
    nota = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Pin en {self.visor.nombre} - {self.activo.nombre if self.activo else 'S/A'}"

    class Meta:
        verbose_name = "Pin de Plano"
        verbose_name_plural = "Pines de Planos"

class PinFoto(models.Model):
    pin = models.ForeignKey(PinPlano, on_delete=models.CASCADE, related_name='fotos')
    imagen = models.ImageField(upload_to='pines/fotos/')
    descripcion = models.CharField(max_length=100, blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Foto de Pin"
        verbose_name_plural = "Fotos de Pines"
