from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime
import uuid
from django.db.models import Max

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

class Requisicion(models.Model):
    """
    Modelo para sincronización de Requisiciones desde Dynamics 365.
    Mapea campos de la entidad cr8ca_requisicion.
    """
    cr8ca_requisicionid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="ID de Requisición (Dynamics)")
    cr8ca_requisicion = models.CharField(max_length=100, unique=True, verbose_name="N° Requisición (REQ-#####-AAAA)")
    cr8ca_asunto = models.CharField(max_length=500, verbose_name="Asunto")
    cr8ca_motivo = models.TextField(null=True, blank=True, verbose_name="Motivo")
    cr8ca_comentarios = models.TextField(null=True, blank=True, verbose_name="Comentarios")
    
    # Totales y Estado
    PRIORIDAD_CHOICES = (
        (1, 'Baja'),
        (2, 'Normal'),
        (3, 'Alta'),
        (4, 'Urgencia'),
        (5, 'Emerencia'),
    )
    cr8ca_totalenarticulos = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Total en Artículos")
    cr8ca_prioridad = models.IntegerField(choices=PRIORIDAD_CHOICES, default=2, null=True, blank=True, verbose_name="Prioridad")
    cr8ca_tipodedocumento = models.IntegerField(null=True, blank=True, verbose_name="Tipo de Documento")
    cr8ca_estatusorden = models.IntegerField(null=True, blank=True, verbose_name="Estatus Orden")
    cr8ca_id_oc = models.CharField(max_length=100, null=True, blank=True, verbose_name="ID OC (Orden de Compra)")
    cr8ca_accion = models.IntegerField(null=True, blank=True, verbose_name="Acción")
    
    # Flags
    cr8ca_ejecutado = models.BooleanField(default=False)
    cr8ca_cerrar = models.BooleanField(default=False)
    cr8ca_cajachica = models.BooleanField(default=False)
    cr8ca_solicituddetabladepago = models.BooleanField(default=False)
    cr8ca_seleccionar = models.BooleanField(default=True)
    
    # Lookups (IDs Externos)
    _cr8ca_presupuesto_value = models.UUIDField(null=True, blank=True)
    _cr8ca_proyecto_value = models.UUIDField(null=True, blank=True)
    _cr8ca_area_value = models.UUIDField(null=True, blank=True)
    _cr8ca_categoria_value = models.UUIDField(null=True, blank=True)
    _cr8ca_departamento_value = models.UUIDField(null=True, blank=True)
    _cr8ca_proveedorasignado_value = models.UUIDField(null=True, blank=True)
    _cr8ca_solicita_value = models.UUIDField(null=True, blank=True)
    _cr8ca_autoriza_value = models.UUIDField(null=True, blank=True)
    _cr8ca_reviso_value = models.UUIDField(null=True, blank=True)
    _ownerid_value = models.UUIDField(null=True, blank=True)
    
    # Fechas y Metadatos
    fecha = models.DateField(null=True, blank=True, verbose_name="Fecha")
    cr8ca_fechadegasto = models.DateTimeField(null=True, blank=True)
    createdon = models.DateTimeField(null=True, blank=True, verbose_name="Creado en Dynamics")
    modifiedon = models.DateTimeField(null=True, blank=True, verbose_name="Modificado en Dynamics")
    versionnumber = models.BigIntegerField(null=True, blank=True)
    statecode = models.IntegerField(null=True, blank=True)
    statuscode = models.IntegerField(null=True, blank=True)
    
    # Wizard state y Flujo de Autorización
    ESTADO_REQUISICION_CHOICES = (
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE', 'En espera de autorización'),
        ('AUTORIZADO', 'Autorizado'),
        ('RECHAZADO', 'Rechazado'),
        ('CANCELADO', 'Cancelado'),
    )
    estado_requisicion = models.CharField(
        max_length=50, 
        choices=ESTADO_REQUISICION_CHOICES, 
        default='BORRADOR',
        verbose_name="Estado de la Requisición"
    )
    wizard_step = models.IntegerField(default=1, verbose_name="Paso del Wizard")
    usuario_solicitante = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Solicitante", related_name='requisiciones_solicitadas')
    usuario_en_nombre_de = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="En nombre de", related_name='requisiciones_en_nombre_de')

    def save(self, *args, **kwargs):
        if not self.cr8ca_requisicion:
            anio_actual = datetime.now().year
            prefix = f"REQ-"
            suffix = f"-{anio_actual}"
            
            # Buscar el correlativo más alto para el año actual
            last_req = Requisicion.objects.filter(
                cr8ca_requisicion__startswith=prefix,
                cr8ca_requisicion__endswith=suffix
            ).order_by('cr8ca_requisicion').last()
            
            if last_req:
                try:
                    # Extraer el número REQ-XXXXX-2026 -> XXXXX
                    current_num_str = last_req.cr8ca_requisicion.replace(prefix, '').replace(suffix, '')
                    current_num = int(current_num_str)
                    new_num = current_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            
            self.cr8ca_requisicion = f"{prefix}{str(new_num).zfill(5)}{suffix}"
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cr8ca_requisicion} - {self.cr8ca_asunto[:50]}"

    @property
    def total_estimado(self):
        return sum(item.subtotal for item in self.articulos.all())

    class Meta:
        verbose_name = "Requisición"
        verbose_name_plural = "Requisiciones"
        ordering = ['-createdon']


class ArticuloRequisicion(models.Model):
    """
    Artículos individuales dentro de una Requisición.
    Mapea campos de cr8ca_itemderequisicions.
    """
    cr8ca_itemderequisicionid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requisicion = models.ForeignKey(
        Requisicion, 
        on_delete=models.CASCADE, 
        related_name='articulos',
        verbose_name="Requisición"
    )
    material = models.ForeignKey(
        'inventarios.Material',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requisiciones',
        verbose_name="Material vinculado"
    )
    
    cr8ca_articulo = models.CharField(max_length=500, verbose_name="Descripción del Artículo")
    cr8ca_cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Cantidad")
    cr8ca_costoaproximado = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Costo Aprox.")
    cr8ca_costoaproximado_base = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    cr8ca_tipo = models.IntegerField(null=True, blank=True)
    
    # Lookups
    _cr8ca_edificiozona_value = models.UUIDField(null=True, blank=True)
    _cr8ca_activo_value = models.UUIDField(null=True, blank=True)
    _cr8ca_catalogo_value = models.UUIDField(null=True, blank=True)
    _cr8ca_unidad_value = models.UUIDField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if self.material:
            # Si no hay descripción manual, usar el nombre del material
            if not self.cr8ca_articulo:
                self.cr8ca_articulo = self.material.nombre
            
            # Si no hay costo aproximado, usar el precio estimado del material
            if not self.cr8ca_costoaproximado or self.cr8ca_costoaproximado == 0:
                self.cr8ca_costoaproximado = self.material.precio_estimado
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cr8ca_articulo} ({self.cr8ca_cantidad})"
    
    @property
    def subtotal(self):
        if self.cr8ca_cantidad and self.cr8ca_costoaproximado:
            return self.cr8ca_cantidad * self.cr8ca_costoaproximado
        return 0
    
    
    # Metadatos
    versionnumber = models.BigIntegerField(null=True, blank=True)
    createdon = models.DateTimeField(null=True, blank=True)
    modifiedon = models.DateTimeField(null=True, blank=True)
    exchangerate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    def __str__(self):
        return f"{self.cr8ca_articulo} ({self.cr8ca_cantidad})"

    class Meta:
        verbose_name = "Artículo de Requisición"
        verbose_name_plural = "Artículos de Requisición"


class DocumentoRequisicion(models.Model):
    """
    Documentos adjuntos a una requisición, almacenados en MinIO.
    """
    requisicion = models.ForeignKey(
        Requisicion, 
        on_delete=models.CASCADE, 
        related_name='documentos',
        verbose_name="Requisición"
    )
    archivo = models.FileField(
        upload_to='requisiciones/%Y/%m/',
        verbose_name="Archivo"
    )
    nombre = models.CharField(
        max_length=255, 
        verbose_name="Nombre/Descripción del Documento",
        blank=True
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre or f"Documento de {self.requisicion}"

    class Meta:
        verbose_name = "Documento de Requisición"
        verbose_name_plural = "Documentos de Requisición"
        ordering = ['-creado_en']
