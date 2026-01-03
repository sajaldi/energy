from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime

class PresupuestoAnual(models.Model):
    """
    Plan financiero anual global.
    """
    ESTADOS = (
        ('PLANIFICACION', 'En Planificación'),
        ('APROBADO', 'Aprobado / Activo'),
        ('CERRADO', 'Cerrado'),
    )
    
    MONEDAS = (
        ('DOP', 'Peso Dominicano'),
        ('USD', 'Dólar Estadounidense'),
        ('EUR', 'Euro'),
    )
    
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Plan")
    anio = models.PositiveIntegerField(
        verbose_name="Año",
        validators=[MinValueValidator(2020), MaxValueValidator(2100)],
        default=datetime.now().year
    )
    moneda = models.CharField(max_length=10, choices=MONEDAS, default='DOP')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PLANIFICACION')
    
    descripcion = models.TextField(blank=True, verbose_name="Descripción / Notas")
    
    elaborado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='planes_presupuestarios'
    )
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} ({self.anio})"

    @property
    def total_proyectado(self):
        return sum(partida.monto_proyectado for partida in self.partidas.all())

    @property
    def total_ejecutado(self):
        return sum(partida.total_ejecutado for partida in self.partidas.all())

    @property
    def porcentaje_ejecucion(self):
        total = self.total_proyectado
        if total == 0:
            return 0
        return int((self.total_ejecutado / total) * 100)

    class Meta:
        verbose_name = "Presupuesto Anual"
        verbose_name_plural = "Presupuestos Anuales"
        ordering = ['-anio', 'nombre']


class PartidaPresupuestaria(models.Model):
    """
    Asignación presupuestaria para una Disciplina específica dentro de un año.
    """
    presupuesto_anual = models.ForeignKey(
        PresupuestoAnual, 
        on_delete=models.CASCADE, 
        related_name='partidas'
    )
    disciplina = models.ForeignKey(
        'documentos.Disciplina', 
        on_delete=models.CASCADE, 
        null=True, blank=True,
        related_name='partidas_presupuestarias',
        verbose_name="Disciplina"
    )
    monto_proyectado = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        verbose_name="Monto Proyectado (Anual)"
    )
    descripcion = models.CharField(max_length=500, blank=True, verbose_name="Referencia/Nota")

    def __str__(self):
        return f"{self.disciplina.nombre} - {self.presupuesto_anual.anio}"

    @property
    def total_ejecutado(self):
        return sum(gasto.monto for gasto in self.gastos.all())

    @property
    def monto_proyectado_calculado(self):
        """Suma de todos los items desglosados."""
        return sum(item.total_anual for item in self.items.all())

    @property
    def saldo_disponible(self):
        # Usamos el proyectado manual si no hay items, o el calculado si los hay
        proyectado = self.monto_proyectado_calculado or self.monto_proyectado
        return proyectado - self.total_ejecutado

    class Meta:
        verbose_name = "Partida por Disciplina"
        verbose_name_plural = "Partidas por Disciplinas"
        unique_together = ('presupuesto_anual', 'disciplina')


class ItemPresupuesto(models.Model):
    """
    Desglose de una partida en conceptos específicos con proyección mensual.
    Esto permite manejar conceptos que se repiten o que ocurren en meses específicos.
    """
    partida = models.ForeignKey(
        PartidaPresupuestaria,
        on_delete=models.CASCADE,
        related_name='items'
    )
    concepto = models.CharField(max_length=200, verbose_name="Concepto/Descripción")
    
    # Proyeccion mensual
    ene = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    feb = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mar = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    abr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    may = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    jun = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    jul = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ago = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sep = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    oct = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    nov = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dic = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Ítem de Presupuesto"
        verbose_name_plural = "Ítems de Presupuesto"

    def __str__(self):
        return f"{self.concepto} ({self.partida.disciplina.nombre})"

    @property
    def total_anual(self):
        return (
            self.ene + self.feb + self.mar + self.abr + 
            self.may + self.jun + self.jul + self.ago + 
            self.sep + self.oct + self.nov + self.dic
        )


class GastoEjecutado(models.Model):
    """
    Registro manual de gastos que afectan una partida presupuestaria.
    """
    partida = models.ForeignKey(
        PartidaPresupuestaria, 
        on_delete=models.CASCADE, 
        related_name='gastos'
    )
    fecha = models.DateField(default=datetime.now)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    descripcion = models.CharField(max_length=255, verbose_name="Concepto de Gasto")
    referencia = models.CharField(max_length=100, blank=True, help_text="N° de Factura, OC o similar")
    
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.fecha} - {self.descripcion} ({self.monto})"

    class Meta:
        verbose_name = "Gasto Ejecutado"
        verbose_name_plural = "Gastos Ejecutados"
        ordering = ['-fecha']
