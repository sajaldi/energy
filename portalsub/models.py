import json
from django.db import models
from django.contrib.auth.models import User
from mantenimiento.models import Empresa, TecnicoPuesto
from presupuestos.models import OrdenCompra


class PerfilContratista(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_contratista')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='usuarios_portal')
    activo = models.BooleanField(default=True)
    cargo = models.CharField(max_length=100, blank=True, null=True, verbose_name='Cargo en la empresa')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Perfil de Contratista'
        verbose_name_plural = 'Perfiles de Contratistas'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} - {self.empresa.nombre}'


class ExpedienteMensual(models.Model):
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('ENVIADO', 'Enviado'),
        ('EN_REVISION', 'En Revisión'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='expedientes')
    mes = models.PositiveIntegerField(verbose_name='Mes')
    anio = models.PositiveIntegerField(verbose_name='Año')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='BORRADOR')
    fecha_envio = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de envío')
    fecha_revision = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de revisión')
    revisado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='expedientes_revisados')
    observaciones = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Expediente Mensual'
        verbose_name_plural = 'Expedientes Mensuales'
        unique_together = ('empresa', 'mes', 'anio')
        ordering = ['-anio', '-mes']

    def __str__(self):
        return f'{self.empresa.nombre} - {self.mes}/{self.anio} ({self.get_estado_display()})'


def oc_document_path(instance, filename):
    return f'ordenes_compra/{instance.orden_compra.numero_oc}/{filename}'


class DocumentoOrdenCompra(models.Model):
    TIPO_DOC_CHOICES = [
        ('FACTURA', 'Factura'),
        ('REPORTE', 'Reporte'),
        ('ESTIMACION', 'Estimación'),
        ('RESPALDO', 'Documento de Respaldo'),
        ('GARANTIA', 'Garantía'),
        ('OTRO', 'Otro'),
    ]

    orden_compra = models.ForeignKey(
        OrdenCompra, on_delete=models.CASCADE,
        related_name='documentos_contratista', verbose_name='Orden de Compra'
    )
    tipo = models.CharField(max_length=20, choices=TIPO_DOC_CHOICES, verbose_name='Tipo de documento')
    archivo = models.FileField(upload_to=oc_document_path, max_length=500, verbose_name='Archivo')
    descripcion = models.CharField(max_length=200, blank=True, null=True, verbose_name='Descripción')
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Subido por')
    es_valido = models.BooleanField(default=True, verbose_name='Válido')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Documento de OC'
        verbose_name_plural = 'Documentos de Órdenes de Compra'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.orden_compra.numero_oc}'


def personal_document_path(instance, filename):
    return f'personal/{instance.tecnico.empresa_id}/{instance.tecnico.id}/{filename}'


class TipoDocumentoPersonal(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name='Nombre')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    orden = models.IntegerField(default=0, verbose_name='Orden')

    class Meta:
        verbose_name = 'Tipo de Documento Personal'
        verbose_name_plural = 'Tipos de Documentos Personales'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class DocumentoPersonal(models.Model):
    tecnico = models.ForeignKey(TecnicoPuesto, on_delete=models.CASCADE, related_name='documentos')
    tipo = models.ForeignKey(TipoDocumentoPersonal, on_delete=models.PROTECT, verbose_name='Tipo de documento')
    archivo = models.FileField(upload_to=personal_document_path, max_length=500, verbose_name='Archivo')
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    es_valido = models.BooleanField(default=True, verbose_name='Válido')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Documento del Personal'
        verbose_name_plural = 'Documentos del Personal'
        unique_together = ('tecnico', 'tipo')
        ordering = ['tipo__orden', 'tipo__nombre']

    def __str__(self):
        return f'{self.tipo.nombre} - {self.tecnico.nombre} {self.tecnico.apellido}'


class TipoEntregable(models.Model):
    nombre = models.CharField(max_length=200, unique=True, verbose_name='Nombre del entregable')
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tipo de Entregable'
        verbose_name_plural = 'Tipos de Entregables'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class EntregableContratista(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='entregables_config')
    tipo_entregable = models.ForeignKey(TipoEntregable, on_delete=models.CASCADE, related_name='configs_por_empresa')
    meses_aplicacion = models.JSONField(null=True, blank=True, default=list,
                                        verbose_name='Meses de aplicación',
                                        help_text='Ej: [1,3,5,7,9,11] para bimensual. Vacío/null = todos los meses')
    obligatorio = models.BooleanField(default=True, verbose_name='Obligatorio')
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Entregable del Contratista'
        verbose_name_plural = 'Entregables del Contratista'
        unique_together = ('empresa', 'tipo_entregable')

    def get_meses(self):
        meses = self.meses_aplicacion
        if not meses:
            return list(range(1, 13))
        if isinstance(meses, str):
            return json.loads(meses)
        return sorted(meses)

    def __str__(self):
        return f'{self.empresa.nombre} - {self.tipo_entregable.nombre}'


def entregable_path(instance, filename):
    return f'entregables/{instance.empresa.id}/{instance.tipo_entregable_id}/{instance.anio}/{instance.mes or 0}/{filename}'


class DocumentoEntregable(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='documentos_entregables')
    tipo_entregable = models.ForeignKey(TipoEntregable, on_delete=models.CASCADE, related_name='documentos_subidos')
    mes = models.PositiveIntegerField(null=True, blank=True, verbose_name='Mes')
    anio = models.PositiveIntegerField(verbose_name='Año')
    archivo = models.FileField(upload_to=entregable_path, max_length=500, verbose_name='Archivo')
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    es_valido = models.BooleanField(default=True, verbose_name='Válido')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Documento de Entregable'
        verbose_name_plural = 'Documentos de Entregables'
        unique_together = ('empresa', 'tipo_entregable', 'mes', 'anio')
        ordering = ['tipo_entregable', 'mes']

    def __str__(self):
        periodo = f' {self.mes}/{self.anio}' if self.mes else f' {self.anio}'
        return f'{self.tipo_entregable.nombre}{periodo} - {self.empresa.nombre}'


class HistorialPersonal(models.Model):
    TIPO_CHOICES = [
        ('ALTA', 'Alta'),
        ('BAJA', 'Baja'),
        ('REINGRESO', 'Reingreso'),
        ('CAMBIO_PUESTO', 'Cambio de Puesto'),
        ('DOCUMENTO', 'Documento Subido'),
        ('OTRO', 'Otro'),
    ]

    tecnico = models.ForeignKey(TecnicoPuesto, on_delete=models.CASCADE, related_name='historial')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name='Tipo de evento')
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Realizado por')
    detalle = models.TextField(blank=True, null=True, verbose_name='Detalle')

    class Meta:
        verbose_name = 'Historial del Personal'
        verbose_name_plural = 'Historial del Personal'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.tecnico.nombre} {self.tecnico.apellido} - {self.fecha.strftime("%d/%m/%Y %H:%M")}'
