from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from datetime import datetime


class AnalisisCostoUnitario(models.Model):
    ESTADOS = (
        ('BORRADOR', 'Borrador'),
        ('APROBADO', 'Aprobado'),
        ('OBSOLETO', 'Obsoleto'),
    )

    codigo = models.CharField(
        max_length=50, unique=True, blank=True,
        help_text="Código único (se genera auto: ACU-YYYY-NNNN)"
    )
    nombre = models.CharField(max_length=300, verbose_name="Nombre / Concepto")
    descripcion = models.TextField(blank=True, verbose_name="Descripción del análisis")

    unidad = models.ForeignKey(
        'inventarios.UnidadMedida', on_delete=models.PROTECT,
        related_name='analisis_costos',
        verbose_name="Unidad de Medida del ACU",
        help_text="Ej: m², m³, pieza, hora, global"
    )
    version = models.PositiveIntegerField(default=1, verbose_name="Versión")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR')

    proyecto = models.ForeignKey(
        'proyectos.Proyecto', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='analisis_costos',
        verbose_name="Proyecto asociado"
    )

    creado_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='analisis_costos_creados'
    )
    aprobado_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='analisis_costos_aprobados'
    )
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Análisis de Costo Unitario"
        verbose_name_plural = "Análisis de Costos Unitarios"
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            year = datetime.now().year
            last = AnalisisCostoUnitario.objects.filter(
                codigo__startswith=f'ACU-{year}-'
            ).order_by('-codigo').first()
            if last:
                try:
                    last_num = int(last.codigo.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            self.codigo = f'ACU-{year}-{next_num:04d}'
        super().save(*args, **kwargs)

    @property
    def costo_directo_total(self):
        return sum(d.total_parcial for d in self.detalles.all())

    @property
    def total_indirectos(self):
        total = Decimal('0')
        for f in self.factores.all():
            if f.tipo == 'PORCENTAJE':
                total += self.costo_directo_total * f.valor / Decimal('100')
            else:
                total += f.valor
        return total

    @property
    def costo_total(self):
        return self.costo_directo_total + self.total_indirectos

    @property
    def factor_total_porcentaje(self):
        base = self.costo_directo_total
        if base == 0:
            return Decimal('0')
        return (self.total_indirectos / base) * Decimal('100')


class DetalleCostoUnitario(models.Model):
    TIPO_RECURSO = (
        ('MATERIAL', 'Material'),
        ('REPUESTO', 'Repuesto'),
        ('MANO_OBRA', 'Mano de Obra'),
        ('EQUIPO', 'Equipo / Maquinaria'),
        ('HERRAMIENTA', 'Herramienta'),
        ('SUBCONTRATO', 'Subcontrato'),
        ('OTRO', 'Otro'),
    )

    analisis = models.ForeignKey(
        AnalisisCostoUnitario, on_delete=models.CASCADE,
        related_name='detalles'
    )
    tipo_recurso = models.CharField(
        max_length=20, choices=TIPO_RECURSO, default='MATERIAL',
        verbose_name="Tipo de Recurso"
    )

    material = models.ForeignKey(
        'inventarios.Material', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='detalles_acu',
        verbose_name="Material / Repuesto (del catálogo)"
    )
    descripcion = models.CharField(
        max_length=500, blank=True,
        verbose_name="Descripción (si no es del catálogo)"
    )
    unidad = models.ForeignKey(
        'inventarios.UnidadMedida', on_delete=models.PROTECT,
        related_name='detalles_acu',
        verbose_name="Unidad del recurso"
    )
    cantidad = models.DecimalField(
        max_digits=12, decimal_places=4, default=1,
        validators=[MinValueValidator(Decimal('0.0001'))],
        verbose_name="Cantidad por unidad de obra"
    )
    precio_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Precio Unitario"
    )
    factor_rendimiento = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal('1.0000'),
        validators=[MinValueValidator(Decimal('0.0001'))],
        verbose_name="Factor de Rendimiento",
        help_text="1.0 = rendimiento nominal. <1 = más eficiente. >1 = desperdicio/ineficiencia."
    )
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Detalle de Recurso"
        verbose_name_plural = "Detalles de Recursos"
        ordering = ['analisis', 'orden', 'id']

    def __str__(self):
        src = self.material.nombre if self.material else (self.descripcion or "Recurso sin nombre")
        return f"{src} x {self.cantidad} {self.unidad.abreviatura}"

    @property
    def total_parcial(self):
        return self.cantidad * self.precio_unitario * self.factor_rendimiento

    @property
    def display_nombre(self):
        if self.material:
            return self.material.nombre
        return self.descripcion or "—"


class FactorCosto(models.Model):
    TIPOS = (
        ('PORCENTAJE', 'Porcentaje (%)'),
        ('MONTO_FIJO', 'Monto Fijo'),
    )

    analisis = models.ForeignKey(
        AnalisisCostoUnitario, on_delete=models.CASCADE,
        related_name='factores'
    )
    nombre = models.CharField(max_length=200, verbose_name="Nombre del factor")
    tipo = models.CharField(max_length=20, choices=TIPOS, default='PORCENTAJE')
    valor = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name="Valor",
        help_text="% si es porcentaje, monto si es fijo"
    )
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Factor de Costo Indirecto"
        verbose_name_plural = "Factores de Costo Indirecto"
        ordering = ['analisis', 'orden', 'id']

    def __str__(self):
        if self.tipo == 'PORCENTAJE':
            return f"{self.nombre}: {self.valor}%"
        return f"{self.nombre}: {self.valor}"
