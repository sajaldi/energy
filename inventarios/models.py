from django.db import models
from django.db.models import Sum
from django.core.validators import MinValueValidator
from decimal import Decimal

class SolicitudMaterial(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('ENTREGADO', 'Entregado / Completado'),
        ('RECHAZADO', 'Rechazado'),
    ]

    usuario = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='solicitudes_inventario')
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE', db_index=True)
    
    orden_trabajo = models.ForeignKey('mantenimiento.OrdenTrabajo', on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_material')
    ubicacion_origen = models.ForeignKey('activos.Ubicacion', on_delete=models.CASCADE, related_name='solicitudes_salida')
    
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
    marca = models.ForeignKey('activos.Marca', on_delete=models.SET_NULL, null=True, blank=True, related_name='materiales', verbose_name="Marca")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    categoria = models.ForeignKey(CategoriaMaterial, on_delete=models.SET_NULL, null=True, blank=True, related_name='materiales', verbose_name="Categoría")
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
    ubicacion_especifica = models.CharField(max_length=100, blank=True, verbose_name="Ubicación Específica (Pasillo/Estante)")
    
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Existencia por Ubicación"
        verbose_name_plural = "Existencias por Ubicación"
        unique_together = ('material', 'ubicacion', 'ubicacion_especifica')

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
    solicitud = models.ForeignKey(SolicitudMaterial, on_delete=models.CASCADE, null=True, blank=True, related_name='items')
    tipo = models.CharField(max_length=15, choices=TIPO_MOVIMIENTO, db_index=True)
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    ubicacion_origen = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_salida')
    ubicacion_destino = models.ForeignKey('activos.Ubicacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos_entrada')
    ubicacion_especifica = models.CharField(max_length=100, blank=True, verbose_name="Ubicación Específica (Destino)")
    
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
            stock, _ = StockRecord.objects.get_or_create(
                material=self.material, 
                ubicacion=self.ubicacion_destino,
                ubicacion_especifica=self.ubicacion_especifica
            )
            stock.cantidad += self.cantidad
            stock.save()
        elif self.tipo == 'SALIDA' and self.ubicacion_origen:
            if self.ubicacion_especifica:
                # Caso 1: Se especificó una ubicación exacta (pasillo, estante, etc.)
                stock = StockRecord.objects.filter(
                    material=self.material, 
                    ubicacion=self.ubicacion_origen,
                    ubicacion_especifica=self.ubicacion_especifica
                ).first()
                if not stock or stock.cantidad < self.cantidad:
                    raise ValueError(f"Stock insuficiente en {self.ubicacion_especifica}. Disponible: {stock.cantidad if stock else 0}")
                stock.cantidad -= self.cantidad
                stock.save()
            else:
                # Caso 2: Pedido general al almacén. Descontar de cualquier celda disponible de forma incremental (Recursivo).
                desc_ids = self.ubicacion_origen.get_descendants().values_list('id', flat=True)
                total_disponible = StockRecord.objects.filter(
                    material=self.material, 
                    ubicacion__in=desc_ids
                ).aggregate(total=Sum('cantidad'))['total'] or 0
                
                if total_disponible < self.cantidad:
                    raise ValueError(f"Stock insuficiente en almacén {self.ubicacion_origen.nombre}. Disponible: {total_disponible}")
                
                pendiente = self.cantidad
                existencias = StockRecord.objects.filter(
                    material=self.material, 
                    ubicacion__in=desc_ids,
                    cantidad__gt=0
                ).order_by('cantidad') # Empezar por las de menor cantidad
                
                for stock in existencias:
                    if pendiente <= 0: break
                    a_descontar = min(stock.cantidad, pendiente)
                    stock.cantidad -= a_descontar
                    stock.save()
                    pendiente -= a_descontar
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
