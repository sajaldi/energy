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
        ('DOP', 'Pesos Dominicanos (DOP)'),
        ('USD', 'Dólares (USD)'),
        ('HNL', 'Lempiras (HNL)'),
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
        return sum(partida.total_gastado for partida in self.partidas.all())

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
    Ahora actúa como la fila principal de la Cost Sheet.
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
        verbose_name="Monto Original (Aprobado)"
    )
    descripcion = models.CharField(max_length=500, blank=True, verbose_name="Referencia/Nota")

    def __str__(self):
        nombre_disc = self.disciplina.nombre if self.disciplina else (self.descripcion or "Partida General")
        return f"{nombre_disc} - {self.presupuesto_anual.anio}"

    # --- Cost Sheet Columns Calculations ---

    @property
    def total_cambios_aprobados(self):
        return sum(
            c.monto for c in self.cambios.filter(estado='APROBADO')
        )

    @property
    def presupuesto_vigente(self):
        """Original Budget + Approved Changes"""
        return self.monto_proyectado + self.total_cambios_aprobados

    @property
    def total_comprometido(self):
        """Sum of approved commitments (Orders/Contracts)"""
        # Sumamos los detalles de compromisos aprobados
        return sum(
            d.monto_comprometido 
            for d in self.detalles_compromiso.filter(compromiso__estado__in=['APROBADO', 'CERRADO'])
        )

    @property
    def pendiente_comprometer(self):
        """Uncommitted Budget = Current Budget - Committed Amount"""
        return self.presupuesto_vigente - self.total_comprometido

    @property
    def total_gastado(self):
        """Actuals / Invoiced Amount"""
        # Sumamos gastos directos o vinculados
        return sum(g.monto for g in self.gastos.all())

    @property
    def pendiente_facturar_compromiso(self):
        """Committed but not yet spent/invoiced"""
        # Este cálculo puede ser complejo si no linkeamos gasto a compromiso explícitamente.
        # Por simplicidad: Comprometido - Gastado (asumiendo que todo gasto sale de un compromiso o afecta el disponible igual)
        # Si Gastado > Comprometido, esto podría ser negativo, indicando sobre-ejecución.
        return self.total_comprometido - self.total_gastado

    @property
    def saldo_disponible(self):
        """Budget Balance currently available (Uncommitted)"""
        return self.pendiente_comprometer
        # Nota: En Unifier, el "Saldo" suele ser el "Uncommitted".
        # Si se quiere "Remaining Budget" (Vigente - Gastado), es otra métrica.
        # Aquí usaremos Uncommitted como saldo operativo para nuevas contrataciones.

    class Meta:
        verbose_name = "Partida por Disciplina"
        verbose_name_plural = "Partidas por Disciplinas"
        unique_together = ('presupuesto_anual', 'disciplina')


class CambioPresupuesto(models.Model):
    """
    Gestión de cambios al presupuesto (Transferencias, Adicionales).
    """
    TIPOS = (
        ('TRANSFERENCIA', 'Transferencia Interna'),
        ('ADICIONAL', 'Presupuesto Adicional'),
        ('REDUCCION', 'Reducción / Ajuste'),
    )
    ESTADOS = (
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE', 'Pendiente de Aprobación'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
    )

    partida = models.ForeignKey(PartidaPresupuestaria, related_name='cambios', on_delete=models.CASCADE)
    monto = models.DecimalField(max_digits=12, decimal_places=2, help_text="Use negativo para reducciones")
    tipo = models.CharField(max_length=20, choices=TIPOS, default='ADICIONAL')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR')
    descripcion = models.CharField(max_length=255)
    fecha_solicitud = models.DateField(default=datetime.now)
    fecha_aprobacion = models.DateField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tipo} - {self.partida} ({self.monto})"

    class Meta:
        verbose_name = "Cambio de Presupuesto"
        verbose_name_plural = "Cambios de Presupuesto"


class Compromiso(models.Model):
    """
    Representa un Contrato, Orden de Compra o Compromiso Directo.
    """
    ESTADOS = (
        ('BORRADOR', 'Borrador'),
        ('APROBADO', 'Aprobado / Emitido'),
        ('CERRADO', 'Cerrado / Completado'),
        ('ANULADO', 'Anulado'),
    )
    
    descripcion = models.CharField(max_length=255, verbose_name="Descripción del Contrato/OC")
    proveedor = models.CharField(max_length=200, verbose_name="Proveedor / Contratista")
    referencia = models.CharField(max_length=100, blank=True, verbose_name="N° Referencia (OC/Contrato)")
    fecha = models.DateField(default=datetime.now)
    monto_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR')
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.referencia} - {self.proveedor}"

    class Meta:
        verbose_name = "Compromiso (Contrato/OC)"
        verbose_name_plural = "Compromisos"
        ordering = ['-fecha']


class DetalleCompromiso(models.Model):
    """
    Línea de detalle de un compromiso que afecta a una partida específica.
    """
    compromiso = models.ForeignKey(Compromiso, related_name='detalles', on_delete=models.CASCADE)
    partida = models.ForeignKey(PartidaPresupuestaria, related_name='detalles_compromiso', on_delete=models.CASCADE)
    monto_comprometido = models.DecimalField(max_digits=12, decimal_places=2)
    descripcion = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Detalle de {self.compromiso} en {self.partida}"

    class Meta:
        verbose_name = "Detalle de Compromiso"
        verbose_name_plural = "Detalles de Compromisos"


class GastoEjecutado(models.Model):
    """
    Registro manual de gastos (Facturas, Pagos).
    Puede estar vinculado a un Compromiso previo o ser directo.
    """
    partida = models.ForeignKey(
        PartidaPresupuestaria, 
        on_delete=models.CASCADE, 
        related_name='gastos'
    )
    compromiso = models.ForeignKey(
        Compromiso,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='gastos_vinculados',
        verbose_name="Compromiso Relacionado"
    )
    fecha = models.DateField(default=datetime.now)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    descripcion = models.CharField(max_length=255, verbose_name="Concepto de Gasto")
    referencia = models.CharField(max_length=100, blank=True, help_text="N° de Factura, OC o similar")
    
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.fecha} - {self.descripcion} ({self.monto})"

    class Meta:
        verbose_name = "Gasto Ejecutado (Factura)"
        verbose_name_plural = "Gastos Ejecutados (Facturas)"
        ordering = ['-fecha']


class ItemPresupuesto(models.Model):
    """
    Desglose de una partida en conceptos específicos.
    Define la regla de recurrencia (Padre).
    """
    FRECUENCIAS = (
        ('MENSUAL', 'Mensual (Todos los meses)'),
        ('BIMESTRAL', 'Bimestral (Cada 2 meses)'),
        ('TRIMESTRAL', 'Trimestral (Cada 3 meses)'),
        ('CUATRIMESTRAL', 'Cuatrimestral (Cada 4 meses)'),
        ('SEMESTRAL', 'Semestral (Cada 6 meses)'),
        ('ANUAL', 'Anual (Una vez al año)'),
        ('MANUAL', 'Manual (Definir mes a mes)'),
    )

    partida = models.ForeignKey(
        PartidaPresupuestaria,
        on_delete=models.CASCADE,
        related_name='items'
    )
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='subitems', 
        verbose_name="Item Padre"
    )
    concepto = models.CharField(max_length=200, verbose_name="Concepto/Descripción")
    
    # Automatización
    es_recurrente = models.BooleanField(default=False, verbose_name="¿Es Recurrente?")
    frecuencia = models.CharField(max_length=20, choices=FRECUENCIAS, default='MANUAL')
    monto_base = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Monto para cada ocurrencia")
    mes_inicio = models.PositiveIntegerField(
        default=1, 
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Mes de comienzo (1=Enero, 12=Diciembre)"
    )

    class Meta:
        verbose_name = "Ítem de Presupuesto"
        verbose_name_plural = "Ítems de Presupuesto"

    def __str__(self):
        return f"{self.concepto} ({self.partida.disciplina.nombre})"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # Solo generar automáticamente al crear. 
        # Para actualizaciones, el usuario usará el botón "Generar Distribución" si desea resetear.
        if is_new and self.es_recurrente and self.frecuencia != 'MANUAL' and self.monto_base > 0:
            self._generar_detalles()

    def _generar_detalles(self):
        # Borrar existentes (Estrategia simple: Full Regen)
        self.detalles.all().delete()
            
        step = 1
        if self.frecuencia == 'BIMESTRAL': step = 2
        if self.frecuencia == 'TRIMESTRAL': step = 3
        if self.frecuencia == 'CUATRIMESTRAL': step = 4
        if self.frecuencia == 'SEMESTRAL': step = 6
        if self.frecuencia == 'ANUAL': step = 12
        
        current_month = self.mes_inicio
        detalles_to_create = []
        while current_month <= 12:
            detalles_to_create.append(
                DetallePeriodico(
                    item=self,
                    mes=current_month,
                    monto=self.monto_base
                )
            )
            current_month += step
        
        if detalles_to_create:
            DetallePeriodico.objects.bulk_create(detalles_to_create)

    @property
    def total_anual(self):
        return sum(d.monto for d in self.detalles.all())


class DetallePeriodico(models.Model):
    """
    Hijo de ItemPresupuesto. Guarda el monto específico para un mes.
    """
    MESES = (
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    )
    
    item = models.ForeignKey(ItemPresupuesto, related_name='detalles', on_delete=models.CASCADE)
    mes = models.PositiveIntegerField(choices=MESES)
    monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Detalle Periódico"
        verbose_name_plural = "Detalles Periódicos"
        ordering = ['mes']
        unique_together = ('item', 'mes')

    def __str__(self):
        return f"{self.get_mes_display()} - {self.monto}"


class PresupuestoAgrupado(models.Model):
    """
    Agrupación de varios presupuestos anuales para visualización gerencial.
    """
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Grupo")
    descripcion = models.TextField(blank=True, verbose_name="Descripción / Notas")
    presupuestos = models.ManyToManyField(
        PresupuestoAnual, 
        related_name='agrupaciones',
        verbose_name="Presupuestos Incluidos"
    )
    anio = models.PositiveIntegerField(
        verbose_name="Año de Referencia",
        validators=[MinValueValidator(2020), MaxValueValidator(2100)],
        default=datetime.now().year
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    @property
    def total_proyectado(self):
        return sum(p.total_proyectado for p in self.presupuestos.all())

    @property
    def total_ejecutado(self):
        return sum(p.total_ejecutado for p in self.presupuestos.all())

    @property
    def porcentaje_ejecucion(self):
        total = self.total_proyectado
        if total == 0:
            return 0
        return int((self.total_ejecutado / total) * 100)

    class Meta:
        verbose_name = "Presupuesto Agrupado"
        verbose_name_plural = "Presupuestos Agrupados"
        ordering = ['-anio', 'nombre']
