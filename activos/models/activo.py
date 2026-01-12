from django.db import models
from django.contrib.auth.models import User

class Marca(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        app_label = 'activos'

class Modelo(models.Model):
    nombre = models.CharField(max_length=100)
    marca = models.ForeignKey(Marca, on_delete=models.CASCADE, related_name='modelos')
    categoria = models.ForeignKey('activos.Categoria', on_delete=models.SET_NULL, null=True, blank=True, related_name='modelos')
    
    imagen_archivo = models.ImageField(upload_to='modelos_fotos/', blank=True, null=True, help_text="Cargar imagen desde el equipo")
    imagen_url = models.URLField(max_length=500, blank=True, null=True, help_text="O pegar una URL externa de la imagen")

    @property
    def imagen(self):
        """Retorna la URL de la imagen, priorizando el archivo cargado."""
        if self.imagen_archivo:
            return self.imagen_archivo.url
        return self.imagen_url

    def __str__(self):
        return f"{self.marca} - {self.nombre}"

    class Meta:
        verbose_name = "Modelo"
        verbose_name_plural = "Modelos"
        app_label = 'activos'

class Activo(models.Model):
    ESTADO_CHOICES = [
        ('OPERATIVO', 'Operativo'),
        ('MANTENIMIENTO', 'En Mantenimiento'),
        ('REPARACION', 'En Reparación'),
        ('FUERA_SERVICIO', 'Fuera de Servicio'),
        ('OBSOLETO', 'Obsoleto/De Baja'),
    ]

    nombre = models.CharField(max_length=200, help_text="Nombre del activo o equipo")
    codigo_interno = models.CharField(max_length=50, unique=True, help_text="Código de inventario interno")
    serie = models.CharField(max_length=100, blank=True, null=True, help_text="Número de serie del fabricante", db_index=True)
    
    marca_legacy = models.CharField(max_length=100, blank=True, null=True)
    modelo_legacy = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.ForeignKey(Modelo, on_delete=models.SET_NULL, null=True, blank=True, related_name='activos')
    
    descripcion = models.TextField(blank=True, null=True)
    
    fecha_compra = models.DateField(blank=True, null=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='OPERATIVO', db_index=True)
    
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='activos_asignados', help_text="Persona responsable del activo")
    
    padre = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='componentes', help_text="Activo principal del cual este forma parte")

    ubicacion_legacy = models.CharField(max_length=255, blank=True, null=True, help_text="Ubicación física del activo (Texto libre - Deprecado)")
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='activos', help_text="Ubicación jerárquica")
    
    foto = models.ImageField(upload_to='activos_fotos/', blank=True, null=True)
    
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    @property
    def tiene_hijos(self):
        """Devuelve True si este activo tiene componentes (hijos). Optimizado para usar anotaciones."""
        if hasattr(self, 'num_hijos'):
            return self.num_hijos > 0
        return self.componentes.exists()

    def __str__(self):
        return f"{self.nombre} ({self.codigo_interno or 'S/C'})"

    class Meta:
        verbose_name = "Activo"
        verbose_name_plural = "Activos"
        app_label = 'activos'
