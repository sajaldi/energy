from django.db import models
from colorfield.fields import ColorField

class TipoMedidor(models.Model):
    """Representa un tipo de medidor."""
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    #verbose
    verbose_name = 'Tipo de Medidor'
    verbose_name_plural = 'Tipos de Medidores'
    def __str__(self) -> str:
        return str(self.nombre)
        
class Medidor(models.Model):
    
    nombre = models.CharField(max_length=50)
    tipo = models.CharField(max_length=50, blank=True, null=True)
    tipo_medidor = models.ForeignKey(TipoMedidor, on_delete=models.CASCADE, null=True, blank=True, related_name='medidores')
    medidor_padre = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='medidores_hijos')
    def __str__(self):
        return self.nombre

class VistaConsumoDiferencia(models.Model):
    medidor_id = models.IntegerField(primary_key=True)  # Django necesita un primary_key
    fecha = models.DateTimeField()
    consumo = models.FloatField()
    consumo_anterior = models.FloatField()
    diferencia_consumo = models.FloatField()

    class Meta:
        managed = False  # Evita que Django intente crear esta tabla
        db_table = 'vista_consumo_diferencia'
        verbose_name = 'Vista Consumo Diferencia'
        verbose_name_plural = 'Vista Consumo Diferencia'
        ordering = ['-fecha']

class Consumo(models.Model):
    fecha = models.DateTimeField()
    consumo = models.FloatField(null=True, blank=True)
    medidor = models.ForeignKey(Medidor, on_delete=models.CASCADE, null=True, blank=True, related_name='consumos')
    
    class Meta:
        unique_together = [['fecha', 'medidor']]
        verbose_name = 'Consumo'
        verbose_name_plural = 'Consumos'

    def __str__(self):
        return f"{self.medidor.nombre if self.medidor else 'Sin medidor'} - {self.fecha} - {self.consumo} kWh"


from django.db import models

class InterfaceConsumo(models.Model):
    fecha = models.DateTimeField(null=True, blank=True)
    consumo = models.FloatField(null=True, blank=True)
    medidor = models.CharField(max_length=50, null=True, blank=True)
    
    class Meta:
        db_table = 'interface_core_consumo'
        managed = True
        unique_together = ['fecha', 'medidor']

        # NO unique_together HERE

from django.db import models

class Equipo(models.Model):
    """Representa un equipo en el sistema."""
    numero_equipo = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self) -> str:
        return str(self.numero_equipo)

class UbicacionTecnica(models.Model):
    """Representa una ubicación técnica en el sistema."""
    codigo_ubicacion = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self) -> str:
        return str(self.codigo_ubicacion)

class CategoriaPuntoMedicion(models.Model):
    """Clasifica los puntos de medición por su tipo."""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return str(self.nombre)

class CaracteristicaMedicion(models.Model):
    """Define la característica que se mide (ej. Temperatura, Presión) y su unidad."""
    nombre = models.CharField(max_length=100, unique=True)
    unidad_medida = models.CharField(max_length=20)
    descripcion = models.TextField(blank=True, null=True)
    # Removed: ambito_medicion_inferior, ambito_medicion_superior, valor_objetivo

    def __str__(self) -> str:
        return f"{self.nombre} ({self.unidad_medida})"

class RangoMedicion(models.Model):
    """Define rangos personalizados para cada característica de medición."""
    caracteristica = models.ForeignKey(
        CaracteristicaMedicion,
        on_delete=models.CASCADE,
        related_name='rangos'
    )
    valor_min = models.FloatField(verbose_name="Valor mínimo")
    valor_max = models.FloatField(verbose_name="Valor máximo")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción")
    color = ColorField(default='#FF0000', verbose_name="Color representativo")
    
    def __str__(self) -> str:
        return f"{self.descripcion} ({self.valor_min} - {self.valor_max})"
    
    class Meta:
        verbose_name = "Rango de Medición"
        verbose_name_plural = "Rangos de Medición"
        ordering = ['caracteristica', 'valor_min']

class PuntoMedicion(models.Model):
    """Representa un punto específico donde se realiza una medición."""
    numero_interno = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=255)
    objeto_tecnico_equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, blank=True, null=True, verbose_name="Equipo Asociado")
    objeto_tecnico_ubicacion = models.ForeignKey(UbicacionTecnica, on_delete=models.CASCADE, blank=True, null=True, verbose_name="Ubicación Técnica Asociada")
    categoria = models.ForeignKey(CategoriaPuntoMedicion, on_delete=models.SET_NULL, blank=True, null=True)
    caracteristica = models.ForeignKey(CaracteristicaMedicion, on_delete=models.PROTECT)
    es_contador = models.BooleanField(default=False, verbose_name="Es Contador")
    # Removed fields: ambito_medicion_inferior, ambito_medicion_superior, valor_objetivo

    def __str__(self) -> str:  # Add explicit return type annotation
        return str(self.descripcion)  # Ensure string conversion

    class Meta:
        verbose_name = "Punto de Medición"
        verbose_name_plural = "Puntos de Medición"

class DocumentoMedicion(models.Model):
    """Registra las lecturas tomadas en los puntos de medición."""
    punto_medicion = models.ForeignKey(PuntoMedicion, on_delete=models.CASCADE)
    fecha_hora_lectura = models.DateTimeField(verbose_name="Fecha y hora de lectura")  # Removed auto_now_add
    valor_leido = models.FloatField()
    lectura_contador = models.FloatField(blank=True, null=True, verbose_name="Lectura de Contador (si aplica)")
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Lectura de {str(self.punto_medicion)} el {self.fecha_hora_lectura}"

    class Meta:
        verbose_name = "Documento de Medición"
        verbose_name_plural = "Documentos de Medición"
        ordering = ['-fecha_hora_lectura']
