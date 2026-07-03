from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime
from django.utils import timezone
import uuid
from django.db.models import Max

class Moneda(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    codigo = models.CharField(max_length=10, unique=True, verbose_name="Código (Siglas)")
    simbolo = models.CharField(max_length=10, default='$', verbose_name="Símbolo")

    def __str__(self):
        return self.codigo

    class Meta:
        verbose_name = "Moneda"
        verbose_name_plural = "Monedas"
        ordering = ['codigo']

class PresupuestoAnual(models.Model):
    """
    Plan financiero anual global.
    """
    ESTADOS = (
        ('PLANIFICACION', 'En Planificación'),
        ('APROBADO', 'Aprobado / Activo'),
        ('CERRADO', 'Cerrado'),
    )
    
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Plan")
    anio = models.PositiveIntegerField(
        verbose_name="Año",
        validators=[MinValueValidator(2020), MaxValueValidator(2100)],
        default=datetime.now().year
    )
    moneda = models.ForeignKey(
        'Moneda',
        on_delete=models.PROTECT,
        related_name='presupuestos',
        verbose_name="Moneda"
    )
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PLANIFICACION')
    departamento = models.ForeignKey(
        'core.Departamento',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='presupuestos',
        verbose_name="Departamento"
    )
    
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

    departamentos = models.ManyToManyField(
        'core.Departamento',
        blank=True,
        related_name='partidas_permitidas',
        verbose_name="Departamentos Permitidos",
        help_text="Si se seleccionan departamentos, solo los usuarios de estos departamentos verán esta partida. Si está vacío, será visible para todos (Global)."
    )

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
        try:
            return f"{self.concepto} ({self.partida.disciplina.nombre})"
        except AttributeError:
            return f"{self.concepto}"
    
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
    isv = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, default=0, verbose_name="ISV (Impuesto Sobre Ventas)")
    cr8ca_prioridad = models.IntegerField(choices=PRIORIDAD_CHOICES, default=2, null=True, blank=True, verbose_name="Prioridad")
    cr8ca_id_oc = models.CharField(max_length=100, null=True, blank=True, verbose_name="ID OC (Orden de Compra)")
    
    # Flags
    cr8ca_ejecutado = models.BooleanField(default=False)
    cr8ca_cerrar = models.BooleanField(default=False)
    cr8ca_cajachica = models.BooleanField(default=False)
    cr8ca_solicituddetabladepago = models.BooleanField(default=False)
    cr8ca_seleccionar = models.BooleanField(default=True)
    
    # Lookups (IDs Externos)
    _ownerid_value = models.UUIDField(null=True, blank=True)
    
    # Fechas y Metadatos
    fecha = models.DateTimeField(default=timezone.now, null=True, blank=True, verbose_name="Fecha")
    fecha_aprobacion = models.DateTimeField(null=True, blank=True, verbose_name="Aprobado el")
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
        ('VISTO_PROCURA', 'Visto por Procura'),
        ('PROCURA_PROCESANDO', 'Procura Procesando'),
        ('EN_ORDEN_COMPRA', 'En Orden de Compra'),
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
    aprobador = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='requisiciones_a_aprobar',
        verbose_name="Aprobador"
    )

    partida = models.ForeignKey(
        'PartidaPresupuestaria',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requisiciones',
        verbose_name="Partida Presupuestaria"
    )

    item_presupuesto = models.ForeignKey(
        'ItemPresupuesto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requisiciones',
        verbose_name="Ítem de Presupuesto"
    )

    tipo_rutina = models.ForeignKey(
        'mantenimiento.Tipo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requisiciones',
        verbose_name="Tipo de Rutina"
    )

    proveedor = models.ForeignKey(
        'mantenimiento.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requisiciones_asignadas',
        verbose_name="Proveedor Asignado"
    )
    proveedores_sugeridos = models.ManyToManyField(
        'mantenimiento.Empresa',
        blank=True,
        related_name='requisiciones_sugeridas',
        verbose_name="Proveedores Sugeridos"
    )
    proveedores_sugeridos_notas = models.TextField(
        null=True, 
        blank=True, 
        verbose_name="Detalle por Proveedor",
        help_text="Especifique qué artículos corresponden a cada proveedor sugerido."
    )

    proyecto = models.ForeignKey(
        'proyectos.Proyecto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requisiciones',
        verbose_name="Proyecto"
    )

    recepcion_notificada = models.BooleanField(
        default=False,
        verbose_name="Notificación de Recepción Enviada"
    )
    fecha_probable_entrega = models.DateField(
        null=True, blank=True,
        verbose_name="Fecha Probable de Entrega"
    )

    def save(self, *args, **kwargs):
        if not self.cr8ca_requisicion:
            from datetime import datetime
            anio_actual = datetime.now().year
            
            # Obtener el código de departamento del usuario solicitante
            dept_code = "GEN"
            if self.usuario_solicitante:
                try:
                    if hasattr(self.usuario_solicitante, 'perfil') and self.usuario_solicitante.perfil.departamento:
                        code = self.usuario_solicitante.perfil.departamento.codigo
                        if code:
                            dept_code = code.strip().upper()
                except Exception:
                    pass
            
            prefix = f"REQ-{dept_code}-"
            suffix = f"-{anio_actual}"
            
            # Encontrar el correlativo más alto para el departamento y año actual
            reqs = Requisicion.objects.filter(
                cr8ca_requisicion__startswith=prefix,
                cr8ca_requisicion__endswith=suffix
            )
            max_num = 0
            for r in reqs:
                try:
                    num_str = r.cr8ca_requisicion[len(prefix):-len(suffix)]
                    val = int(num_str)
                    if val > max_num:
                        max_num = val
                except (ValueError, IndexError):
                    pass
            
            new_num = max_num + 1
            self.cr8ca_requisicion = f"{prefix}{str(new_num).zfill(3)}{suffix}"
            
        if not self.fecha:
            self.fecha = timezone.now()

        # Auto-poblar aprobador desde el departamento del solicitante si no tiene uno asignado
        if not self.aprobador and self.usuario_solicitante:
            try:
                dept = self.usuario_solicitante.perfil.departamento
                if dept and dept.aprobador:
                    self.aprobador = dept.aprobador
            except Exception:
                pass
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cr8ca_requisicion} - {self.cr8ca_asunto[:50]}"

    @property
    def moneda(self):
        if self.partida and self.partida.presupuesto_anual:
            return self.partida.presupuesto_anual.moneda
        return None

    @property
    def total_estimado(self):
        return sum((item.cr8ca_cantidad or 0) * (item.cr8ca_costoaproximado or 0) for item in self.articulos.all())

    def get_total_by_provider(self, provider):
        """Calcula el subtotal para un proveedor específico"""
        articles = self.articulos.filter(proveedor=provider) if provider else self.articulos.filter(proveedor__isnull=True)
        return sum((item.cr8ca_cantidad or 0) * (item.cr8ca_costoaproximado or 0) for item in articles)


    @property
    def monto_pagado(self):
        """Suma de montos en solicitudes de pago con estatus PAGADO"""
        return sum(item.monto_solicitado for item in self.items_pago.filter(estatus='PAGADO'))

    @property
    def monto_pagado_negativo(self):
        """Monto pagado multiplicado por -1 para facilitar restas en templates usando |add"""
        return self.monto_pagado * -1

    @property
    def resumen_por_proveedor(self):
        """Retorna una lista de diccionarios con proveedor, sus artículos y el subtotal"""
        from mantenimiento.models import Empresa
        resumen = []
        # Obtener IDs de proveedores únicos vinculados a artículos de esta requisición
        provider_ids = self.articulos.values_list('proveedor', flat=True).distinct()
        
        for p_id in provider_ids:
            provider = Empresa.objects.get(pk=p_id) if p_id else None
            articles = self.articulos.filter(proveedor=p_id)
            subtotal = sum(a.subtotal for a in articles)
            resumen.append({
                'proveedor': provider,
                'articulos': articles,
                'subtotal': subtotal
            })
        return resumen

    class Meta:
        verbose_name = "Requisición"
        verbose_name_plural = "Requisiciones"
        ordering = ['-createdon']


class ArticuloRequisicion(models.Model):
    """
    Artículos individuales dentro de una Requisición.
    Mapea campos de cr8ca_itemderequisicions.
    """
    cr8ca_itemderequisicionid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=True, null=False, blank=True)
    requisicion = models.ForeignKey(
        Requisicion, 
        on_delete=models.CASCADE, 
        related_name='articulos',
        verbose_name="Requisición"
    )
    proveedor = models.ForeignKey(
        'mantenimiento.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articulos_requisicion',
        verbose_name="Proveedor sugerido para este artículo"
    )
    material = models.ForeignKey(
        'inventarios.Material',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requisiciones',
        verbose_name="Material vinculado"
    )
    
    cr8ca_articulo = models.CharField(max_length=1000, verbose_name="Descripción del Artículo")
    cr8ca_cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Cantidad")
    cr8ca_costoaproximado = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Costo Aprox.")
    cr8ca_costoaproximado_base = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    cr8ca_tipo = models.IntegerField(null=True, blank=True)
    
    # Lookups
    _cr8ca_edificiozona_value = models.UUIDField(null=True, blank=True)
    _cr8ca_activo_value = models.UUIDField(null=True, blank=True)

    @property
    def subtotal(self):
        return (self.cr8ca_cantidad or 0) * (self.cr8ca_costoaproximado or 0)
    _cr8ca_catalogo_value = models.UUIDField(null=True, blank=True)
    _cr8ca_unidad_value = models.UUIDField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Generate UUID if not provided
        if not self.cr8ca_itemderequisicionid:
            self.cr8ca_itemderequisicionid = uuid.uuid4()
            
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

    def get_proxy_url(self):
        """Retorna la URL para previsualizar el archivo vía proxy"""
        if not self.archivo: return ""
        from django.conf import settings
        from django.urls import reverse
        path = reverse('presupuestos:requisicion_documento_proxy', args=[self.id])
        return f"{settings.SITE_URL.rstrip('/')}{path}"

    def __str__(self):
        return self.nombre or f"Documento de {self.requisicion}"

    class Meta:
        verbose_name = "Documento de Requisición"
        verbose_name_plural = "Documentos de Requisición"
        ordering = ['-creado_en']


class SolicitudPago(models.Model):
    """
    Agrupa varias solicitudes de pago de distintas requisiciones.
    """
    ESTADOS = (
        ('ABIERTA', 'Abierta'),
        ('EN_REVISION', 'En Revisión'),
        ('CERRADA', 'Cerrada'),
    )

    descripcion = models.CharField(max_length=255, verbose_name="Descripción Global/Referencia")
    fecha_solicitud = models.DateField(default=datetime.now, verbose_name="Fecha de Solicitud")
    usuario_solicitante = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='solicitudes_pago',
        verbose_name="Solicitante"
    )
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ABIERTA')
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Solicitud {self.pk} - {self.descripcion}"

    @property
    def total_solicitado(self):
        """Suma de montos de items con estatus PAGADO o SOLICITADO"""
        return sum(item.monto_solicitado for item in self.items.all() if item.estatus in ['PAGADO', 'SOLICITADO'])

    @property
    def total_aprobado(self):
        """Suma de montos con estatus APROBADO"""
        return sum(item.monto_solicitado for item in self.items.all() if item.estatus == 'APROBADO')

    @property
    def total_pagado(self):
        """Suma de montos con estatus PAGADO"""
        return sum(item.monto_solicitado for item in self.items.all() if item.estatus == 'PAGADO')

    class Meta:
        verbose_name = "Solicitud de Pago"
        verbose_name_plural = "Solicitudes de Pago"
        ordering = ['-fecha_solicitud']


class ItemSolicitudPago(models.Model):
    """
    Item individual de una solicitud de pago, vinculado a una requisición.
    """
    ESTATUS_CHOICES = (
        ('SOLICITADO', 'Solicitado'),
        ('APROBADO', 'Aprobado'),
        ('PAGADO', 'Pagado'),
        ('POSPUESTO', 'Pospuesto'),
        ('RECHAZADO', 'Rechazado'),
    )

    CONDICION_PAGO_CHOICES = (
        ('CONTADO', 'Al Contado'),
        ('ANTICIPO', 'Anticipo'),
        ('DIFERIDO', 'Diferido'),
        ('CREDITO', 'A Plazos / Crédito'),
        ('CONTRA_ENTREGA', 'Contra Entrega'),
    )

    solicitud = models.ForeignKey(
        SolicitudPago, 
        on_delete=models.CASCADE, 
        related_name='items',
        verbose_name="Solicitud Padre"
    )
    requisicion = models.ForeignKey(
        Requisicion, 
        on_delete=models.CASCADE, 
        related_name='items_pago',
        verbose_name="Requisición Vinculada"
    )
    
    monto_solicitado = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Monto Solicitado")
    condicion_pago = models.CharField(
        max_length=20, 
        choices=CONDICION_PAGO_CHOICES, 
        null=True, 
        blank=True, 
        verbose_name="Condición de Pago"
    )
    descripcion = models.CharField(
        max_length=500, 
        verbose_name="Descripción del Pago",
        help_text="Ej: Anticipo, Pago Parcial, Pago Final"
    )
    estatus = models.CharField(max_length=20, choices=ESTATUS_CHOICES, default='SOLICITADO', verbose_name="Estatus del Item")
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Pago para {self.requisicion} - {self.monto_solicitado}"

    class Meta:
        verbose_name = "Ítem de Solicitud de Pago"
        verbose_name_plural = "Ítems de Solicitud de Pago"
        unique_together = ('solicitud', 'requisicion')


class NotaRequisicion(models.Model):
    """
    Notas internas con timestamp y usuario para el timeline de una requisición.
    """
    requisicion = models.ForeignKey(
        Requisicion,
        on_delete=models.CASCADE,
        related_name='notas',
        verbose_name="Requisición"
    )
    texto = models.TextField(verbose_name="Nota")
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Usuario"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.creado_en.strftime('%d/%m/%Y %H:%M')} - {self.usuario}: {self.texto[:50]}"

    class Meta:
        verbose_name = "Nota de Requisición"
        verbose_name_plural = "Notas de Requisición"
        ordering = ['-creado_en']


class RequisicionHistorial(models.Model):
    requisicion = models.ForeignKey(
        Requisicion, on_delete=models.CASCADE,
        related_name='historial', verbose_name="Requisición"
    )
    estado_anterior = models.CharField(
        max_length=50, null=True, blank=True, verbose_name="Estado Anterior",
        choices=Requisicion.ESTADO_REQUISICION_CHOICES
    )
    estado_nuevo = models.CharField(
        max_length=50, verbose_name="Estado Nuevo",
        choices=Requisicion.ESTADO_REQUISICION_CHOICES
    )
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Usuario"
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha del Cambio")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Historial de Requisición"
        verbose_name_plural = "Historial de Requisiciones"
        ordering = ['creado_en']

    def __str__(self):
        return f"{self.creado_en.strftime('%d/%m/%Y %H:%M')} | {self.estado_anterior or '---'} → {self.estado_nuevo}"


class REPEX(models.Model):
    """
    Replacement Expenditure - Plan de reposición de activos.
    """
    ESTADOS = (
        ('BORRADOR', 'Borrador'),
        ('APROBADO', 'Aprobado'),
        ('EJECUCION', 'En Ejecución'),
        ('CERRADO', 'Cerrado'),
    )

    nombre = models.CharField(max_length=200, verbose_name="Nombre del Plan")
    anio = models.PositiveIntegerField(
        verbose_name="Año",
        validators=[MinValueValidator(2020), MaxValueValidator(2100)],
        default=datetime.now().year
    )
    descripcion = models.TextField(blank=True, verbose_name="Descripción / Notas")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR')
    
    creado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='planes_repex'
    )
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"REPEX {self.anio} - {self.nombre}"

    @property
    def costo_total_reposicion(self):
        return sum(item.costo_reposicion for item in self.items.all())

    @property
    def ahorro_proyectado(self):
        # Diferencia opcional si aplica, o simplemente métrica de CAPEX
        return sum(item.costo_reposicion for item in self.items.all())

    class Meta:
        verbose_name = "Plan REPEX"
        verbose_name_plural = "Planes REPEX"
        ordering = ['-anio', 'nombre']


class REPEXItem(models.Model):
    """
    Item individual de un plan REPEX.
    Puede estar vinculado a un activo o ser un ítem manual (ej: reposición masiva).
    """
    PRIORIDADES = (
        ('ALTA', 'Alta (Crítico)'),
        ('MEDIA', 'Media'),
        ('BAJA', 'Baja'),
    )

    repex = models.ForeignKey(REPEX, related_name='items', on_delete=models.CASCADE)
    activo = models.ForeignKey('activos.Activo', on_delete=models.CASCADE, related_name='repex_items', null=True, blank=True, help_text="Dejar vacío para ítems manuales")
    modelo = models.ForeignKey('activos.Modelo', on_delete=models.SET_NULL, null=True, blank=True, related_name='repex_items_manuales', help_text="Modelo asociado para ítems manuales")
    
    # Campos para ítems manuales (sin activo vinculado)
    nombre_item = models.CharField(max_length=300, blank=True, help_text="Nombre descriptivo cuando no hay activo vinculado")
    ubicacion_manual = models.CharField(max_length=300, blank=True, help_text="Ubicación manual (ej: Edificio A → Nivel 2)")
    categoria_manual = models.CharField(max_length=300, blank=True, help_text="Categoría del ítem (ej: Iluminación, Plomería)")
    unidades = models.CharField(max_length=50, blank=True, help_text="Unidad de medida (ej: pieza, metro, lote)")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=1, help_text="Cantidad de unidades")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Precio por unidad")

    descripcion = models.CharField(max_length=500, blank=True, help_text="Motivo de la reposición")
    costo_original = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Costo original del sistema")
    costo_reposicion = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Costo total (cantidad × precio unitario)")
    
    fecha_proyectada = models.DateField(null=True, blank=True)
    prioridad = models.CharField(max_length=10, choices=PRIORIDADES, default='MEDIA')
    justificacion = models.TextField(blank=True)

    @property
    def es_manual(self):
        """True si el ítem no tiene activo vinculado."""
        return self.activo is None

    @property
    def display_nombre(self):
        """Nombre para mostrar: del activo o manual."""
        if self.activo:
            return str(self.activo.nombre)
        return self.nombre_item or 'Ítem sin nombre'

    def save(self, *args, **kwargs):
        # Auto-calcular costo si hay cantidad y precio unitario
        if self.cantidad and self.precio_unitario:
            self.costo_reposicion = self.cantidad * self.precio_unitario
        # Jalar costo original del activo si existe
        if self.activo and not self.costo_original and self.activo.costo:
            self.costo_original = self.activo.costo
        super().save(*args, **kwargs)

    def __str__(self):
        nombre = self.display_nombre
        return f"Reponer {nombre} - {self.repex.nombre}"

    class Meta:
        verbose_name = "Ítem REPEX"
        verbose_name_plural = "Ítems REPEX"


class CentroCosto(models.Model):
    nombre = models.CharField(max_length=200, verbose_name="Centro de Costo")
    descripcion = models.TextField(null=True, blank=True, verbose_name="Descripción")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Centro de Costo"
        verbose_name_plural = "Centros de Costo"
        ordering = ['nombre']


class OrdenCompra(models.Model):
    TIPO_DOC_CHOICES = (
        ('OC', 'OC'),
        ('DOIH', 'DOIH'),
    )
    ESTADO_OC_CHOICES = (
        ('BORRADOR', 'Borrador'),
        ('ENVIADA', 'Enviada a Proveedor'),
        ('CONFIRMADA', 'Confirmada'),
        ('RECIBIDA', 'Recibida'),
        ('CANCELADA', 'Cancelada'),
    )
    tipo_documento = models.CharField(max_length=10, choices=TIPO_DOC_CHOICES, default='OC', verbose_name="Tipo Documento")
    numero_oc = models.CharField(max_length=50, unique=True, verbose_name="N° Orden de Compra")
    requisicion = models.ForeignKey(
        Requisicion, on_delete=models.CASCADE,
        related_name='ordenes_compra', verbose_name="Requisición"
    )
    proveedor = models.ForeignKey(
        'mantenimiento.Empresa', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordenes_compra',
        verbose_name="Proveedor"
    )
    estado = models.CharField(max_length=20, choices=ESTADO_OC_CHOICES, default='BORRADOR', verbose_name="Estado")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_entrega_estimada = models.DateField(null=True, blank=True, verbose_name="Fecha de entrega estimada")
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Subtotal")
    impuestos = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Impuestos")
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Total")
    creado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordenes_compra_creadas', verbose_name="Creado por"
    )
    notas = models.TextField(null=True, blank=True, verbose_name="Notas")
    centro_costo = models.ForeignKey(
        CentroCosto, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordenes_compra', verbose_name="Centro de Costo"
    )
    anticipo = models.BooleanField(default=False, verbose_name="Anticipo")
    anticipo_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="% Anticipo")
    contraentrega = models.BooleanField(default=False, verbose_name="Contraentrega")
    credito = models.BooleanField(default=False, verbose_name="Crédito")
    credito_dias = models.IntegerField(null=True, blank=True, verbose_name="Días de crédito")
    doc_factura = models.BooleanField(default=False, verbose_name="Factura")
    doc_estimacion = models.BooleanField(default=False, verbose_name="Estimación")
    doc_respaldo = models.BooleanField(default=False, verbose_name="Respaldo")
    doc_garantia = models.BooleanField(default=False, verbose_name="Garantía")

    def save(self, *args, **kwargs):
        if not self.numero_oc:
            from datetime import datetime
            anio = str(datetime.now().year)[-2:]
            tipo = self.tipo_documento or 'OC'
            if tipo == 'DOIH':
                oc_prefix = f"DOIH_OC{anio}-"
            else:
                oc_prefix = f"OC{anio}-"
            correlativo = OrdenCompra.objects.filter(
                numero_oc__startswith=oc_prefix
            ).count() + 1
            self.numero_oc = f"{oc_prefix}{str(correlativo).zfill(3)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.numero_oc

    class Meta:
        verbose_name = "Orden de Compra"
        verbose_name_plural = "Órdenes de Compra"
        ordering = ['-fecha_creacion']


class OrdenCompraArticulo(models.Model):
    orden_compra = models.ForeignKey(
        OrdenCompra, on_delete=models.CASCADE,
        related_name='articulos', verbose_name="Orden de Compra"
    )
    articulo_requisicion = models.ForeignKey(
        ArticuloRequisicion, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordenes_compra_articulos',
        verbose_name="Artículo de Requisición"
    )
    descripcion = models.CharField(max_length=1000, verbose_name="Descripción")
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Cantidad")
    costo_unitario = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Costo Unitario")
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Subtotal")

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.costo_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.descripcion[:50]} ({self.cantidad})"

    class Meta:
        verbose_name = "Artículo de Orden de Compra"
        verbose_name_plural = "Artículos de Órdenes de Compra"


class ItemPredefinido(models.Model):
    disciplina = models.ForeignKey(
        'documentos.Disciplina', on_delete=models.CASCADE,
        related_name='items_predefinidos', verbose_name="Disciplina"
    )
    codigo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código")
    descripcion = models.TextField(verbose_name="Descripción")
    unidad_medida = models.CharField(max_length=50, verbose_name="Unidad de Medida")
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Precio Unitario")
    moneda = models.ForeignKey(
        'Moneda', on_delete=models.PROTECT,
        related_name='items_predefinidos', verbose_name="Moneda"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")

    def __str__(self):
        return f"{self.codigo or ''} - {self.descripcion[:60]}"

    class Meta:
        verbose_name = "Item Predefinido"
        verbose_name_plural = "Items Predefinidos"
        ordering = ['disciplina', 'codigo']


class Cotizacion(models.Model):
    ESTADOS = [
        ('BORRADOR', 'Borrador'),
        ('ENVIADA', 'Enviada'),
        ('APROBADA', 'Aprobada'),
        ('RECHAZADA', 'Rechazada'),
    ]
    numero = models.CharField(max_length=20, unique=True, verbose_name="Número de Cotización")
    proyecto = models.ForeignKey(
        'proyectos.Proyecto', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cotizaciones',
        verbose_name="Proyecto"
    )
    disciplina = models.ForeignKey(
        'documentos.Disciplina', on_delete=models.PROTECT,
        related_name='cotizaciones', verbose_name="Disciplina"
    )
    fecha = models.DateField(verbose_name="Fecha")
    valida_hasta = models.DateField(null=True, blank=True, verbose_name="Válida Hasta")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR', verbose_name="Estado")
    creado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='cotizaciones', verbose_name="Creado por"
    )
    notas = models.TextField(blank=True, verbose_name="Notas")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    @property
    def subtotal(self):
        return sum(i.total for i in self.items.all())

    @property
    def descuento_total(self):
        return sum(i.total * (i.descuento_porcentaje / 100) for i in self.items.all())

    @property
    def total(self):
        return self.subtotal

    def __str__(self):
        return f"{self.numero} - {self.disciplina}"

    class Meta:
        verbose_name = "Cotización"
        verbose_name_plural = "Cotizaciones"
        ordering = ['-creado_en']


class ItemCotizacion(models.Model):
    cotizacion = models.ForeignKey(
        Cotizacion, on_delete=models.CASCADE,
        related_name='items', verbose_name="Cotización"
    )
    item_predefinido = models.ForeignKey(
        ItemPredefinido, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='items_cotizacion',
        verbose_name="Item Predefinido"
    )
    descripcion = models.TextField(verbose_name="Descripción")
    unidad_medida = models.CharField(max_length=50, verbose_name="Unidad de Medida")
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Precio Unitario")
    descuento_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name="Descuento %"
    )
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")

    @property
    def total(self):
        return self.cantidad * self.precio_unitario * (1 - self.descuento_porcentaje / 100)

    def __str__(self):
        return f"{self.descripcion[:50]} ({self.cantidad})"

    class Meta:
        verbose_name = "Item de Cotización"
        verbose_name_plural = "Items de Cotización"
        ordering = ['orden']
