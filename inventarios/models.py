from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

class Material(models.Model):
    UNIDAD_CHOICES = [
        ('UNIDAD', 'Unidad'),
        ('LITRO', 'Litro'),
        ('GALON', 'Galón'),
        ('KG', 'Kilogramo'),
        ('METRO', 'Metro'),
        ('CAJA', 'Caja'),
    ]

    nombre = models.CharField(max_length=200, db_index=True, verbose_name="Nombre del Material")
    sku = models.CharField(max_length=50, unique=True, db_index=True, verbose_name="SKU / Código Interno")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    unidad_medida = models.CharField(max_length=20, choices=UNIDAD_CHOICES, default='UNIDAD')
    precio_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0.00'))])
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Alerta cuando el stock total baje de este nivel")
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def get_stock_total(self):
        return self.existencias.aggregate(total=models.Sum('cantidad'))['total'] or 0

    def __str__(self):
        return f"{self.nombre} ({self.sku})"

    class Meta:
        verbose_name = "Material / Repuesto"
        verbose_name_plural = "Materiales y Repuestos"
        ordering = ['nombre']

class CompatibilidadMaterial(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='modelos_compatibles')
    modelo = models.ForeignKey('activos.Modelo', on_delete=models.CASCADE, related_name='repuestos_sugeridos')
    cantidad_sugerida = models.DecimalField(max_digits=10, decimal_places=2, default=1, help_text="Cantidad usual requerida para este modelo")
    notas = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Compatibilidad de Repuesto"
        verbose_name_plural = "Compatibilidades de Repuestos"
        unique_together = ('material', 'modelo')

class StockRecord(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='existencias')
    ubicacion = models.ForeignKey('activos.Ubicacion', on_delete=models.CASCADE, related_name='inventario')
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Existencia por Ubicación"
        verbose_name_plural = "Existencias por Ubicación"
        unique_together = ('material', 'ubicacion')

    def __str__(self):
        return f"{self.material.nombre} en {self.ubicacion.nombre}: {self.cantidad}"

class MovimientoInventario(models.Model):
    TIPO_MOVIMIENTO = [
        ('ENTRADA', 'Entrada (Compra/Carga)'),
        ('SALIDA', 'Salida (Uso/Retiro)'),
        ('AJUSTE', 'Ajuste de Inventario'),
        ('TRASLADO', 'Traslado entre Ubicaciones'),
    ]

    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='movimientos')
    tipo = models.CharField(max_length=15, choices=TIPO_MOVIMIENTO, db_index=True)
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    ubicacion_origen = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_salida')
    ubicacion_destino = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_entrada')
    
    orden_trabajo = models.ForeignKey('mantenimiento.OrdenTrabajo', on_delete=models.SET_NULL, null=True, blank=True, related_name='materiales_usados')
    usuario = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    
    comentarios = models.TextField(blank=True, null=True)
    fecha_movimiento = models.DateTimeField(auto_now_add=True, db_index=True)

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
        """
        if self.estado == 'APROBADO':
            return # Ya fue procesado
            
        from django.utils import timezone
        
        # Lógica para actualizar StockRecord (Movida desde save())
        if self.tipo == 'ENTRADA' and self.ubicacion_destino:
            stock, _ = StockRecord.objects.get_or_create(material=self.material, ubicacion=self.ubicacion_destino)
            stock.cantidad += self.cantidad
            stock.save()
        elif self.tipo == 'SALIDA' and self.ubicacion_origen:
            stock, _ = StockRecord.objects.get_or_create(material=self.material, ubicacion=self.ubicacion_origen)
            if stock.cantidad < self.cantidad:
                raise ValueError(f"Stock insuficiente para liquidar. Disponible: {stock.cantidad}")
            stock.cantidad -= self.cantidad
            stock.save()
        elif self.tipo == 'TRASLADO' and self.ubicacion_origen and self.ubicacion_destino:
            # Restar de origen
            stock_orig, _ = StockRecord.objects.get_or_create(material=self.material, ubicacion=self.ubicacion_origen)
            if stock_orig.cantidad < self.cantidad:
                raise ValueError(f"Stock insuficiente en origen. Disponible: {stock_orig.cantidad}")
            stock_orig.cantidad -= self.cantidad
            stock_orig.save()
            # Sumar a destino
            stock_dest, _ = StockRecord.objects.get_or_create(material=self.material, ubicacion=self.ubicacion_destino)
            stock_dest.cantidad += self.cantidad
            stock_dest.save()
        elif self.tipo == 'AJUSTE' and self.ubicacion_destino:
            stock, _ = StockRecord.objects.get_or_create(material=self.material, ubicacion=self.ubicacion_destino)
            stock.cantidad += self.cantidad
            stock.save()

        self.estado = 'APROBADO'
        self.aprobado_por = usuario_aprobador
        self.fecha_aprobacion = timezone.now()
        self.save()

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
