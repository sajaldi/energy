from django.db import models
from django.db.models import Sum
from django.core.validators import MinValueValidator
from decimal import Decimal

class SolicitudMaterial(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE_AUTORIZACION', 'Pendiente de Autorización'),
        ('PENDIENTE', 'Pendiente'),
        ('ENTREGADO', 'Entregado / Completado'),
        ('RECHAZADO', 'Rechazado'),
    ]

    usuario = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='solicitudes_inventario')
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='PENDIENTE', db_index=True)
    
    orden_trabajo = models.ForeignKey('mantenimiento.OrdenTrabajo', on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_material')
    ubicacion_origen = models.ForeignKey('activos.Ubicacion', on_delete=models.CASCADE, related_name='solicitudes_salida')
    
    edificio_destino = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_edificio', verbose_name="Edificio Destino")
    nivel_destino = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_nivel', verbose_name="Nivel Destino")
    
    comentarios_solicitud = models.TextField(blank=True, null=True)
    comentarios_almacen = models.TextField(blank=True, null=True)
    
    fecha_entrega = models.DateTimeField(null=True, blank=True)
    entregado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_despachadas')

    def __str__(self):
        return f"Orden #{self.id} - {self.usuario.username}"

    @property
    def solicitante_nombre(self):
        """Retorna el nombre completo del usuario o su username."""
        return self.usuario.get_full_name() or self.usuario.username

    @property
    def items_count(self):
        """Retorna el conteo de materiales en la orden."""
        return self.items.count()

    class Meta:
        verbose_name = "Solicitud de Material (Orden)"
        verbose_name_plural = "Solicitudes de Material (Órdenes)"
        ordering = ['-fecha_solicitud']

class CategoriaMaterial(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Categoría")
    padre = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategorias', verbose_name="Categoría Padre")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Categoría de Material"
        verbose_name_plural = "Categorías de Materiales"
        ordering = ['nombre']

    def __str__(self):
        if self.padre:
            return f"{self.padre} > {self.nombre}"
        return self.nombre

class UnidadMedida(models.Model):
    nombre = models.CharField(max_length=50, unique=True, verbose_name="Nombre de la Unidad")
    abreviatura = models.CharField(max_length=10, unique=True, verbose_name="Abreviatura")

    class Meta:
        verbose_name = "Unidad de Medida"
        verbose_name_plural = "Unidades de Medida"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.abreviatura})"

class Material(models.Model):
    nombre = models.CharField(max_length=200, db_index=True, verbose_name="Nombre del Material")
    sku = models.CharField(max_length=50, unique=True, db_index=True, verbose_name="SKU / Código Interno")
    marca = models.ForeignKey('activos.Marca', on_delete=models.SET_NULL, null=True, blank=True, related_name='materiales', verbose_name="Marca")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    categoria = models.ForeignKey(CategoriaMaterial, on_delete=models.SET_NULL, null=True, blank=True, related_name='materiales', verbose_name="Categoría")
    unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT, related_name='materiales', verbose_name="Unidad de Medida", null=True, blank=True)
    precio_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0.00'))])
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Alerta cuando el stock total baje de este nivel")
    
    TIPO_MATERIAL_CHOICES = [
        ('INSUMO', 'Insumo'),
        ('REPUESTO', 'Repuesto'),
        ('CONSUMIBLE', 'Consumible'),
        ('MEDICAMENTO', 'Medicamento'),
        ('HERRAMIENTA', 'Herramienta'),
        ('EPP', 'Equipo de Protección (EPP)'),
        ('OTRO', 'Otro'),
    ]
    tipo_material = models.CharField(max_length=20, choices=TIPO_MATERIAL_CHOICES, default='INSUMO', verbose_name="Tipo de Material")
    imagen = models.ImageField(upload_to='materiales/', verbose_name="Imagen del Material", blank=True, null=True)
    
    departamentos = models.ManyToManyField(
        'core.Departamento', 
        blank=True, 
        related_name='materiales_permitidos', 
        verbose_name="Departamentos Permitidos",
        help_text="Si se seleccionan departamentos, solo los usuarios de estos departamentos podrán utilizar este material. Si está vacío, cualquier usuario podrá utilizarlo (Global)."
    )
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def get_stock_total(self):
        return self.existencias.aggregate(total=models.Sum('cantidad'))['total'] or Decimal('0.00')

    def recalcular_stock(self):
        """
        Recalcula las existencias por ubicación y lote desde cero, iterando
        todos los Movimientos de Inventario del material que estén 'APROBADO'.
        """
        movs = self.movimientos.filter(estado='APROBADO')
        stock_map = {}

        for m in movs:
            if m.tipo in ['ENTRADA', 'AJUSTE'] and m.ubicacion_destino_id:
                k = (m.ubicacion_destino_id, m.lote_id, m.ubicacion_especifica)
                stock_map[k] = stock_map.get(k, Decimal('0')) + m.cantidad
            
            # Ajuste también puede restar si especifica origen
            if m.tipo == 'AJUSTE' and m.ubicacion_origen_id:
                k = (m.ubicacion_origen_id, m.lote_id, m.ubicacion_especifica)
                stock_map[k] = stock_map.get(k, Decimal('0')) - m.cantidad

            if m.tipo == 'SALIDA' and m.ubicacion_origen_id:
                k = (m.ubicacion_origen_id, m.lote_id, m.ubicacion_especifica)
                stock_map[k] = stock_map.get(k, Decimal('0')) - m.cantidad
            
            if m.tipo == 'TRASLADO':
                if m.ubicacion_origen_id:
                    k = (m.ubicacion_origen_id, m.lote_id, m.ubicacion_especifica)
                    stock_map[k] = stock_map.get(k, Decimal('0')) - m.cantidad
                if m.ubicacion_destino_id:
                    k = (m.ubicacion_destino_id, m.lote_id, m.ubicacion_especifica)
                    stock_map[k] = stock_map.get(k, Decimal('0')) + m.cantidad
        
        # Reset current stock values instead of deleting them entirely to avoid breaking references
        self.existencias.update(cantidad=Decimal('0'))

        from .models import StockRecord
        for (u_id, l_id, u_esp), qty in stock_map.items():
            if qty != Decimal('0'):
                StockRecord.objects.update_or_create(
                    material=self,
                    ubicacion_id=u_id,
                    lote_id=l_id,
                    ubicacion_especifica=u_esp,
                    defaults={'cantidad': qty}
                )

    def __str__(self):
        return f"{self.nombre} ({self.sku})"

    class Meta:
        verbose_name = "Material / Repuesto"
        verbose_name_plural = "Materiales y Repuestos"
        ordering = ['nombre']

class FotoMaterial(models.Model):
    """
    Permite asociar múltiples fotos a un solo material (ej. placa, estado, empaque).
    """
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='fotos_adicionales', verbose_name="Material")
    imagen = models.ImageField(upload_to='materiales/fotos/', verbose_name="Imagen")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Foto de Material"
        verbose_name_plural = "Fotos de Materiales"

class CompatibilidadMaterial(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='modelos_compatibles')
    modelo = models.ForeignKey('activos.Modelo', on_delete=models.CASCADE, related_name='repuestos_sugeridos')
    cantidad_sugerida = models.DecimalField(max_digits=10, decimal_places=2, default=1, help_text="Cantidad usual requerida para este modelo")
    notas = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Compatibilidad de Repuesto"
        verbose_name_plural = "Compatibilidades de Repuestos"
        unique_together = ('material', 'modelo')

class Lote(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='lotes')
    codigo = models.CharField(max_length=50, verbose_name="Código de Lote")
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de Vencimiento")
    fecha_fabricacion = models.DateField(null=True, blank=True, verbose_name="Fecha de Fabricación")
    
    creado_en = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Lote"
        verbose_name_plural = "Lotes"
        unique_together = ('material', 'codigo')
        ordering = ['fecha_vencimiento']

    def __str__(self):
        return f"Lote {self.codigo} (Vence: {self.fecha_vencimiento})"

class IngresoInventario(models.Model):
    """
    Agrupa un conjunto de materiales que entran al inventario en un mismo momento.
    """
    usuario = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='ingresos_materiales', verbose_name="Recibido por")
    fecha_ingreso = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Ingreso")
    ubicacion_destino = models.ForeignKey('activos.Ubicacion', on_delete=models.CASCADE, related_name='ingresos_recibidos')
    requisicion_origen = models.ForeignKey('presupuestos.Requisicion', on_delete=models.SET_NULL, null=True, blank=True, related_name='ingresos_asociados')
    comentarios = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Ingreso #{self.id} - {self.fecha_ingreso.strftime('%d/%m/%Y')} - {self.usuario.username}"

    class Meta:
        verbose_name = "Ingreso de Material"
        verbose_name_plural = "Ingresos de Materiales"
        ordering = ['-fecha_ingreso']

class FotoIngreso(models.Model):
    ingreso = models.ForeignKey(IngresoInventario, on_delete=models.CASCADE, related_name='fotos', verbose_name="Ingreso")
    imagen = models.ImageField(upload_to='ingresos/fotos/', verbose_name="Foto del Ingreso")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Foto de Ingreso"
        verbose_name_plural = "Fotos de Ingresos"

class FotoDespacho(models.Model):
    solicitud = models.ForeignKey(SolicitudMaterial, on_delete=models.CASCADE, related_name='fotos', verbose_name="Solicitud")
    imagen = models.ImageField(upload_to='despachos/fotos/', verbose_name="Foto del Despacho")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Foto de Despacho"
        verbose_name_plural = "Fotos de Despachos"

    def save(self, *args, **kwargs):
        if self.imagen:
            from core.image_utils import compress_image
            self.imagen = compress_image(self.imagen)
        super().save(*args, **kwargs)

class StockRecord(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='existencias')
    lote = models.ForeignKey(Lote, on_delete=models.CASCADE, null=True, blank=True, related_name='existencias_lote')
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.CASCADE, related_name='inventario')
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ubicacion_especifica = models.CharField(max_length=100, blank=True, verbose_name="Ubicación Específica (Pasillo/Estante)")
    
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Existencia por Ubicación"
        verbose_name_plural = "Existencias por Ubicación"
        unique_together = ('material', 'lote', 'ubicacion', 'ubicacion_especifica')

    def __str__(self):
        lote_str = f" - {self.lote}" if self.lote else ""
        return f"{self.material.nombre} en {self.ubicacion.nombre}{lote_str}: {self.cantidad}"

class MovimientoInventario(models.Model):
    TIPO_MOVIMIENTO = [
        ('ENTRADA', 'Entrada (Compra/Carga)'),
        ('SALIDA', 'Salida (Uso/Retiro)'),
        ('AJUSTE', 'Ajuste de Inventario'),
        ('TRASLADO', 'Traslado entre Ubicaciones'),
    ]

    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='movimientos')
    lote = models.ForeignKey(Lote, on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos')
    solicitud = models.ForeignKey(SolicitudMaterial, on_delete=models.CASCADE, null=True, blank=True, related_name='items')
    ingreso = models.ForeignKey(IngresoInventario, on_delete=models.CASCADE, null=True, blank=True, related_name='detalles', verbose_name="Ingreso relacionado")
    devolucion = models.ForeignKey('DevolucionMaterial', on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_relacionados', verbose_name="Devolución relacionada")
    tipo = models.CharField(max_length=15, choices=TIPO_MOVIMIENTO, db_index=True)
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], verbose_name="Cantidad Entregada/Real")
    cantidad_solicitada = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Cantidad Solicitada")
    ubicacion_origen = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_salida')
    ubicacion_destino = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_entrada')
    ubicacion_especifica = models.CharField(max_length=100, blank=True, verbose_name="Ubicación Específica (Destino)")
    
    orden_trabajo = models.ForeignKey('mantenimiento.OrdenTrabajo', on_delete=models.SET_NULL, null=True, blank=True, related_name='materiales_usados')
    usuario = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    
    comentarios = models.TextField(blank=True, null=True)
    fecha_movimiento = models.DateTimeField(auto_now_add=True, db_index=True)
    es_inconsistente = models.BooleanField(default=False, verbose_name="Inconsistente (Sin Stock)")

    estado = models.CharField(
        max_length=20, 
        choices=[('PENDIENTE', 'Pendiente'), ('APROBADO', 'Aprobado / Liquidado'), ('RECHAZADO', 'Rechazado')],
        default='PENDIENTE',
        db_index=True
    )
    aprobado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_aprobados')
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)

    def liquidar(self, usuario_aprobador):
        """
        Aprueba el movimiento y actualiza el stock real.
        Si no hay stock suficiente, marca como inconsistente pero permite el proceso.
        """
        if self.estado == 'APROBADO':
            return # Ya fue procesado
            
        from django.utils import timezone
        
        # Validaciones Previas (Verificar stock pero no bloquear)
        if self.tipo in ['SALIDA', 'TRASLADO'] and self.ubicacion_origen:
            stock_record = None
            if self.lote:
                stock_record = StockRecord.objects.filter(
                    material=self.material, lote=self.lote,
                    ubicacion=self.ubicacion_origen, ubicacion_especifica=self.ubicacion_especifica
                ).first()
            else:
                stock_record = StockRecord.objects.filter(
                    material=self.material, lote=None,
                    ubicacion=self.ubicacion_origen, ubicacion_especifica=self.ubicacion_especifica
                ).first()
            
            if not stock_record or stock_record.cantidad < self.cantidad:
                # Marcar como inconsistente para auditoría posterior
                self.es_inconsistente = True
                if self.comentarios:
                    self.comentarios += f" | INCONSISTENCIA: Stock teórico insuficiente ({stock_record.cantidad if stock_record else 0})."
                else:
                    self.comentarios = f"INCONSISTENCIA: Stock teórico insuficiente ({stock_record.cantidad if stock_record else 0})."

        # Establecer estado como aprobado para que la señal reconstruya el stock
        self.estado = 'APROBADO'
        self.aprobado_por = usuario_aprobador
        self.fecha_aprobacion = timezone.now()
        self.save()  # Esto disparará la auto-reconstrucción a través de la Señal

    def save(self, *args, **kwargs):
        # NOTA: Ya no actualizamos stock aquí automáticamente para requerir aprobación.
        # Solo guardamos el registro.
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"
        ordering = ['-fecha_movimiento']
        permissions = [
            ("can_liquidar_movimiento", "Puede liquidar/aprobar movimientos de inventario"),
        ]

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver([post_save, post_delete], sender=MovimientoInventario)
def trigger_stock_recalculation(sender, instance, **kwargs):
    """
    Cada vez que se guarda o elimina un Movimiento de Inventario, 
    se recalcula todo el stock de su material correspondiente.
    Esto garantiza 100% de trazabilidad entre Movimientos y Existencias.
    """
    if instance.material_id:
        instance.material.recalcular_stock()

class DevolucionMaterial(models.Model):
    usuario_recibe = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='devoluciones_recibidas', verbose_name="Recibido por")
    persona_devuelve = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='materiales_devueltos', verbose_name="Persona que Devuelve")
    fecha_devolucion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Devolución")
    ubicacion_destino = models.ForeignKey('activos.Ubicacion', on_delete=models.CASCADE, related_name='devoluciones_destino', verbose_name="Ubicación de Destino")
    comentarios = models.TextField(blank=True, null=True, verbose_name="Comentarios / Observaciones")

    class Meta:
        verbose_name = "Devolución de Material"
        verbose_name_plural = "Devoluciones de Materiales"
        ordering = ['-fecha_devolucion']

    def __str__(self):
        return f"Devolución #{self.id} - {self.persona_devuelve} ({self.fecha_devolucion.strftime('%d/%m/%Y')})"

class ItemDevolucion(models.Model):
    ESTADO_MATERIAL = [
        ('NUEVO', 'Nuevo'),
        ('USADO', 'Usado'),
    ]
    devolucion = models.ForeignKey(DevolucionMaterial, on_delete=models.CASCADE, related_name='items')
    material_original = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='items_devueltos')
    material_recibido = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='devoluciones_como_recibido')
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    estado_fisico = models.CharField(max_length=20, choices=ESTADO_MATERIAL, default='NUEVO')
    
    def __str__(self):
        return f"{self.material_recibido.nombre} x {self.cantidad}"

class FotoDevolucion(models.Model):
    devolucion = models.ForeignKey(DevolucionMaterial, on_delete=models.CASCADE, related_name='fotos')
    imagen = models.ImageField(upload_to='inventarios/devoluciones/')
    creado_en = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.imagen:
            from core.image_utils import compress_image
            self.imagen = compress_image(self.imagen)
        super().save(*args, **kwargs)
