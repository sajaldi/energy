from datetime import date, timedelta

from django.db import models, transaction
from django.db.models import Subquery, OuterRef
from django.db.models.signals import m2m_changed, post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.core.validators import MinValueValidator, MaxValueValidator, MinLengthValidator
from django.core.exceptions import ValidationError
from django.utils import timezone


class Riesgo(models.Model):
    """
    Modelo principal de Riesgo de Negocio asociado a un Servicio.
    Implementa ISO 31000:2018 para identificación y registro de riesgos.
    """
    CATEGORIA_CHOICES = [
        ('OPERACIONAL', 'Operacional'),
        ('FINANCIERO', 'Financiero'),
        ('ESTRATEGICO', 'Estratégico'),
        ('CUMPLIMIENTO', 'Cumplimiento'),
        ('REPUTACIONAL', 'Reputacional'),
    ]
    ESTADO_CHOICES = [
        ('ACTIVO', 'Activo'),
        ('CERRADO', 'Cerrado'),
    ]
    ESTADO_APETITO_CHOICES = [
        ('ACEPTABLE', 'Aceptable'),
        ('EN_VIGILANCIA', 'En Vigilancia'),
        ('REQUIERE_ACCION', 'Requiere Acción Inmediata'),
    ]
    ESTADO_REVISION_CHOICES = [
        ('AL_DIA', 'Al día'),
        ('PROXIMA', 'Próxima revisión'),
        ('VENCIDA', 'Revisión vencida'),
    ]
    CICLO_CHOICES = [
        ('MENSUAL', 'Mensual (30 días)'),
        ('BIMESTRAL', 'Bimestral (60 días)'),
        ('TRIMESTRAL', 'Trimestral (90 días)'),
        ('SEMESTRAL', 'Semestral (180 días)'),
        ('ANUAL', 'Anual (365 días)'),
    ]
    CICLO_DIAS = {
        'MENSUAL': 30,
        'BIMESTRAL': 60,
        'TRIMESTRAL': 90,
        'SEMESTRAL': 180,
        'ANUAL': 365,
    }

    codigo = models.CharField(max_length=20, unique=True, editable=False)
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(max_length=2000)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    fuente_riesgo = models.CharField(max_length=500)
    consecuencias = models.TextField(max_length=1000)
    control_existente = models.TextField(max_length=1000, blank=True, default='')

    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='ACTIVO')
    estado_apetito = models.CharField(
        max_length=20, choices=ESTADO_APETITO_CHOICES, default='ACEPTABLE'
    )
    estado_revision = models.CharField(
        max_length=10, choices=ESTADO_REVISION_CHOICES, default='AL_DIA'
    )

    servicio = models.ForeignKey(
        'servicios.Servicio', on_delete=models.CASCADE, related_name='riesgos'
    )
    responsable = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='riesgos_asignados'
    )
    kpis = models.ManyToManyField(
        'servicios.KPI', blank=True, related_name='riesgos_asociados'
    )

    ciclo_revision = models.CharField(
        max_length=15, choices=CICLO_CHOICES, default='TRIMESTRAL'
    )
    proxima_revision = models.DateField(null=True, blank=True)

    fecha_identificacion = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='riesgos_creados'
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Riesgo"
        verbose_name_plural = "Riesgos"
        ordering = ['-fecha_identificacion']
        permissions = [
            ('approve_plantratamiento', 'Puede aprobar planes de tratamiento'),
            ('configure_apetito', 'Puede configurar apetito y tolerancia'),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.titulo}"

    def clean(self):
        """
        Valida campos obligatorios y longitudes máximas del Riesgo.
        Recolecta TODOS los errores y lanza un único ValidationError.
        Requirements: 1.7, 1.8.
        """
        errors = {}

        # Campos obligatorios: no vacíos ni solo espacios en blanco
        campos_obligatorios = {
            'titulo': self.titulo,
            'descripcion': self.descripcion,
            'categoria': self.categoria,
            'fuente_riesgo': self.fuente_riesgo,
            'consecuencias': self.consecuencias,
        }
        for campo, valor in campos_obligatorios.items():
            if not valor or not str(valor).strip():
                errors[campo] = "Este campo es obligatorio."

        # Validaciones de longitud máxima
        limites = {
            'titulo': (self.titulo, 200, "El título no puede exceder 200 caracteres."),
            'descripcion': (self.descripcion, 2000, "La descripción no puede exceder 2000 caracteres."),
            'fuente_riesgo': (self.fuente_riesgo, 500, "La fuente del riesgo no puede exceder 500 caracteres."),
            'consecuencias': (self.consecuencias, 1000, "Las consecuencias no pueden exceder 1000 caracteres."),
            'control_existente': (self.control_existente, 1000, "El control existente no puede exceder 1000 caracteres."),
        }
        for campo, (valor, max_len, mensaje) in limites.items():
            if valor and len(valor) > max_len:
                # No sobrescribir si ya tiene error de campo obligatorio
                if campo not in errors:
                    errors[campo] = mensaje

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._generar_codigo()
        super().save(*args, **kwargs)

    def _generar_codigo(self):
        """
        Genera código único con formato [CÓDIGO_SERVICIO]-R-[0001].
        Busca el último número secuencial para el Servicio y lo incrementa.
        Usa select_for_update para manejar concurrencia y evitar códigos duplicados.
        """
        codigo_servicio = (
            self.servicio.codigo
            if self.servicio.codigo
            else self.servicio.nombre[:5].upper()
        )
        prefix = f"{codigo_servicio}-R-"

        with transaction.atomic():
            ultimo_riesgo = (
                Riesgo.objects
                .select_for_update()
                .filter(servicio=self.servicio)
                .filter(codigo__startswith=prefix)
                .order_by('-codigo')
                .first()
            )

            if ultimo_riesgo:
                try:
                    ultimo_numero = int(ultimo_riesgo.codigo.split('-R-')[1])
                    siguiente_numero = ultimo_numero + 1
                except (ValueError, IndexError):
                    siguiente_numero = 1
            else:
                siguiente_numero = 1

        return f"{prefix}{siguiente_numero:04d}"

    def actualizar_estado_apetito(self):
        """
        Calcula y actualiza el estado_apetito del riesgo basado en la última
        evaluación residual vs los umbrales de apetito/tolerancia del Servicio.

        Clasificación:
        - 'ACEPTABLE': nivel_riesgo_residual <= apetito_riesgo
        - 'EN_VIGILANCIA': apetito_riesgo < nivel_riesgo_residual <= (apetito_riesgo + tolerancia_offset)
        - 'REQUIERE_ACCION': nivel_riesgo_residual > (apetito_riesgo + tolerancia_offset)
        """
        # Obtener la última evaluación residual
        ultima_evaluacion_residual = (
            self.evaluaciones
            .filter(tipo='RESIDUAL')
            .order_by('-fecha_evaluacion')
            .first()
        )

        if not ultima_evaluacion_residual:
            return

        nivel_riesgo_residual = ultima_evaluacion_residual.nivel_riesgo

        # Obtener la configuración de apetito/tolerancia del Servicio
        try:
            config = self.servicio.config_riesgo
        except ConfiguracionRiesgoServicio.DoesNotExist:
            # Crear configuración por defecto si no existe
            config = ConfiguracionRiesgoServicio.objects.create(
                servicio=self.servicio
            )

        apetito = config.apetito_riesgo
        tolerancia = apetito + config.tolerancia_offset

        # Clasificar estado
        if nivel_riesgo_residual <= apetito:
            nuevo_estado = 'ACEPTABLE'
        elif nivel_riesgo_residual <= tolerancia:
            nuevo_estado = 'EN_VIGILANCIA'
        else:
            nuevo_estado = 'REQUIERE_ACCION'

        # Solo guardar si cambió el estado
        if self.estado_apetito != nuevo_estado:
            self.estado_apetito = nuevo_estado
            self.save(update_fields=['estado_apetito', 'fecha_actualizacion'])

    def actualizar_proxima_revision(self, fecha_revision_completada):
        """
        Calcula y guarda la próxima fecha de revisión sumando los días
        del ciclo configurado a la fecha de revisión completada.
        """
        dias = self.CICLO_DIAS[self.ciclo_revision]
        self.proxima_revision = fecha_revision_completada + timedelta(days=dias)
        self.save(update_fields=['proxima_revision'])

    def calcular_estado_revision(self):
        """
        Calcula el estado de revisión basado en los días restantes
        hasta la próxima fecha de revisión:
        - 'AL_DIA': más de 7 días restantes o sin revisión programada
        - 'PROXIMA': entre 1 y 7 días restantes
        - 'VENCIDA': 0 o menos días restantes
        """
        if self.proxima_revision is None:
            return 'AL_DIA'
        days_remaining = (self.proxima_revision - date.today()).days
        if days_remaining > 7:
            return 'AL_DIA'
        elif days_remaining >= 1:
            return 'PROXIMA'
        else:
            return 'VENCIDA'

    def actualizar_estado_revision(self):
        """
        Calcula el estado de revisión y lo guarda si ha cambiado.
        """
        nuevo_estado = self.calcular_estado_revision()
        if self.estado_revision != nuevo_estado:
            self.estado_revision = nuevo_estado
            self.save(update_fields=['estado_revision'])


class EvaluacionRiesgo(models.Model):
    """
    Evaluación de probabilidad e impacto de un riesgo.
    Calcula automáticamente nivel_riesgo (P×I) y zona_riesgo.
    Soporta evaluación inherente (sin controles) y residual (con controles).
    """
    TIPO_CHOICES = [
        ('INHERENTE', 'Riesgo Inherente'),
        ('RESIDUAL', 'Riesgo Residual'),
    ]

    riesgo = models.ForeignKey(
        Riesgo, on_delete=models.CASCADE, related_name='evaluaciones'
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    probabilidad = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    impacto = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    nivel_riesgo = models.IntegerField(editable=False, default=0)
    zona_riesgo = models.CharField(max_length=10, editable=False, default='BAJO')
    justificacion_probabilidad = models.TextField(
        validators=[MinLengthValidator(10)], max_length=1000
    )
    justificacion_impacto = models.TextField(
        validators=[MinLengthValidator(10)], max_length=1000
    )

    evaluado_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    fecha_evaluacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evaluación de Riesgo"
        verbose_name_plural = "Evaluaciones de Riesgo"
        ordering = ['-fecha_evaluacion']

    def __str__(self):
        return f"{self.riesgo.codigo} - {self.get_tipo_display()} ({self.nivel_riesgo})"

    def save(self, *args, **kwargs):
        self.nivel_riesgo = self.probabilidad * self.impacto
        self.zona_riesgo = self._calcular_zona()
        super().save(*args, **kwargs)

    def _calcular_zona(self):
        """
        Clasifica la zona de riesgo según el nivel calculado:
        - Bajo: 1-4
        - Medio: 5-9
        - Alto: 10-16
        - Crítico: 17-25
        """
        nr = self.probabilidad * self.impacto
        if nr <= 4:
            return 'BAJO'
        elif nr <= 9:
            return 'MEDIO'
        elif nr <= 16:
            return 'ALTO'
        else:
            return 'CRITICO'


class ConfiguracionRiesgoServicio(models.Model):
    """
    Configuración de apetito y tolerancia al riesgo por Servicio.
    El umbral de tolerancia (apetito + offset) no puede exceder 25.
    """
    servicio = models.OneToOneField(
        'servicios.Servicio', on_delete=models.CASCADE, related_name='config_riesgo'
    )
    apetito_riesgo = models.IntegerField(
        default=9,
        validators=[MinValueValidator(1), MaxValueValidator(25)],
        help_text="Nivel de riesgo máximo aceptable (1-25)"
    )
    tolerancia_offset = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Offset de tolerancia por encima del apetito (1-10)"
    )
    modificado_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de Riesgo por Servicio"
        verbose_name_plural = "Configuraciones de Riesgo por Servicio"

    def __str__(self):
        return f"Config Riesgo - {self.servicio.nombre} (Apetito: {self.apetito_riesgo})"

    def clean(self):
        if self.apetito_riesgo + self.tolerancia_offset > 25:
            raise ValidationError(
                'El umbral de tolerancia (apetito + offset) no puede superar 25.'
            )

    @property
    def umbral_tolerancia(self):
        """Retorna el umbral de tolerancia efectivo (máximo 25)."""
        return min(self.apetito_riesgo + self.tolerancia_offset, 25)

    def recalcular_estados_riesgos(self):
        """
        Recalcula el estado_apetito de todos los riesgos activos del Servicio
        según los umbrales actuales de apetito y tolerancia.

        Usa una subconsulta anotada para obtener el nivel_riesgo de la última
        evaluación RESIDUAL de cada riesgo, y luego bulk_update para eficiencia.
        Debe completarse en <5 segundos para 200 riesgos.
        """
        apetito = self.apetito_riesgo
        umbral = self.umbral_tolerancia

        # Subconsulta: obtener nivel_riesgo de la evaluación RESIDUAL más reciente
        ultima_eval_residual = (
            EvaluacionRiesgo.objects
            .filter(riesgo=OuterRef('pk'), tipo='RESIDUAL')
            .order_by('-fecha_evaluacion')
            .values('nivel_riesgo')[:1]
        )

        # Obtener todos los riesgos activos con su nivel residual anotado
        riesgos_activos = (
            Riesgo.objects
            .filter(servicio=self.servicio, estado='ACTIVO')
            .annotate(nivel_residual=Subquery(ultima_eval_residual))
        )

        riesgos_a_actualizar = []
        for riesgo in riesgos_activos:
            nivel_residual = riesgo.nivel_residual
            if nivel_residual is None:
                # Sin evaluación residual: se considera aceptable
                nuevo_estado = 'ACEPTABLE'
            elif nivel_residual <= apetito:
                nuevo_estado = 'ACEPTABLE'
            elif nivel_residual <= umbral:
                nuevo_estado = 'EN_VIGILANCIA'
            else:
                nuevo_estado = 'REQUIERE_ACCION'

            if riesgo.estado_apetito != nuevo_estado:
                riesgo.estado_apetito = nuevo_estado
                riesgos_a_actualizar.append(riesgo)

        if riesgos_a_actualizar:
            Riesgo.objects.bulk_update(riesgos_a_actualizar, ['estado_apetito'])


class PlanTratamiento(models.Model):
    """
    Plan de tratamiento para un Riesgo.
    Define la estrategia (Mitigar, Transferir, Evitar, Aceptar) y acciones a ejecutar.
    Valida que fecha_limite sea posterior a fecha_inicio.
    """
    ESTRATEGIA_CHOICES = [
        ('MITIGAR', 'Mitigar'),
        ('TRANSFERIR', 'Transferir'),
        ('EVITAR', 'Evitar'),
        ('ACEPTAR', 'Aceptar'),
    ]
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('APROBADO', 'Aprobado'),
        ('EN_EJECUCION', 'En Ejecución'),
        ('IMPLEMENTADO', 'Implementado'),
        ('CANCELADO', 'Cancelado'),
    ]

    riesgo = models.OneToOneField(
        Riesgo, on_delete=models.CASCADE, related_name='plan_tratamiento'
    )
    estrategia = models.CharField(max_length=15, choices=ESTRATEGIA_CHOICES)
    descripcion_acciones = models.TextField(max_length=2000)
    responsable = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='planes_tratamiento'
    )
    fecha_inicio = models.DateField()
    fecha_limite = models.DateField()
    recursos_requeridos = models.TextField(max_length=1000)
    justificacion_aceptacion = models.TextField(
        max_length=2000, blank=True, default=''
    )
    estado = models.CharField(
        max_length=15, choices=ESTADO_CHOICES, default='BORRADOR'
    )
    nivel_riesgo_esperado = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(25)],
        help_text="Nivel de riesgo esperado tras implementación del plan (1-25)"
    )

    class Meta:
        verbose_name = "Plan de Tratamiento"
        verbose_name_plural = "Planes de Tratamiento"
        ordering = ['-fecha_inicio']

    def __str__(self):
        return f"Plan {self.get_estrategia_display()} - {self.riesgo.codigo}"

    def clean(self):
        errors = {}

        # 1. Validación de fechas: fecha_limite > fecha_inicio
        if self.fecha_limite and self.fecha_inicio and self.fecha_limite <= self.fecha_inicio:
            errors['fecha_limite'] = 'La fecha límite debe ser posterior a la fecha de inicio.'

        # 2. Validación condicional por estrategia
        if self.estrategia in ('MITIGAR', 'TRANSFERIR', 'EVITAR'):
            # Solo validar acciones en planes existentes (al crear no hay pk aún)
            if self.pk and self.acciones.count() == 0:
                errors.setdefault('estrategia', []).append(
                    'Los planes con estrategia Mitigar, Transferir o Evitar requieren al menos una acción.'
                )
        elif self.estrategia == 'ACEPTAR':
            if not self.justificacion_aceptacion or not self.justificacion_aceptacion.strip():
                errors['justificacion_aceptacion'] = (
                    'La estrategia Aceptar requiere una justificación de aceptación.'
                )

        if errors:
            raise ValidationError(errors)

    @property
    def advertencia_nivel_esperado(self):
        """
        Retorna una advertencia (string) si el nivel_riesgo_esperado no reduciría
        el nivel de riesgo residual actual. Retorna None si no aplica.
        Requirement 4.9: advertencia no bloqueante.
        """
        if not self.pk or self.nivel_riesgo_esperado is None:
            return None

        # Obtener la última evaluación RESIDUAL del riesgo asociado
        ultima_eval_residual = (
            self.riesgo.evaluaciones
            .filter(tipo='RESIDUAL')
            .order_by('-fecha_evaluacion')
            .first()
        )

        if ultima_eval_residual is None:
            return None

        if self.nivel_riesgo_esperado >= ultima_eval_residual.nivel_riesgo:
            return (
                f'El nivel de riesgo esperado ({self.nivel_riesgo_esperado}) '
                f'no es menor que el nivel de riesgo residual actual '
                f'({ultima_eval_residual.nivel_riesgo}). '
                f'El plan no reduciría el nivel de riesgo.'
            )

        return None

    def get_advertencias(self):
        """
        Retorna una lista de advertencias (warnings) no bloqueantes
        asociadas a este plan de tratamiento.
        """
        advertencias = []
        adv_nivel = self.advertencia_nivel_esperado
        if adv_nivel:
            advertencias.append(adv_nivel)
        return advertencias


class AccionTratamiento(models.Model):
    """
    Acción individual dentro de un PlanTratamiento.
    Cada acción tiene un estado que puede progresar de PENDIENTE a COMPLETADA.
    fecha_completada se registra cuando la acción se marca como completada.
    """
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_PROGRESO', 'En Progreso'),
        ('COMPLETADA', 'Completada'),
        ('CANCELADA', 'Cancelada'),
    ]

    plan = models.ForeignKey(
        PlanTratamiento, on_delete=models.CASCADE, related_name='acciones'
    )
    descripcion = models.CharField(max_length=500)
    fecha_limite = models.DateField()
    responsable = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='acciones_tratamiento'
    )
    estado = models.CharField(
        max_length=15, choices=ESTADO_CHOICES, default='PENDIENTE'
    )
    fecha_completada = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Acción de Tratamiento"
        verbose_name_plural = "Acciones de Tratamiento"
        ordering = ['fecha_limite']

    def __str__(self):
        return f"{self.descripcion[:50]} ({self.get_estado_display()})"

    def save(self, *args, **kwargs):
        # Auto-set fecha_completada when estado transitions to COMPLETADA
        if self.estado == 'COMPLETADA' and not self.fecha_completada:
            self.fecha_completada = timezone.now()
        elif self.estado != 'COMPLETADA':
            self.fecha_completada = None
        super().save(*args, **kwargs)


class RevisionRiesgo(models.Model):
    """
    Registro de una revisión periódica completada de un Riesgo.
    Almacena los valores anteriores y nuevos de probabilidad/impacto,
    junto con la justificación del cambio o confirmación de valores.
    """
    riesgo = models.ForeignKey(
        Riesgo, on_delete=models.CASCADE, related_name='revisiones'
    )
    probabilidad_anterior = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    impacto_anterior = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    probabilidad_nueva = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    impacto_nueva = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    justificacion = models.TextField(
        validators=[MinLengthValidator(10)], max_length=500
    )
    revisado_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    fecha_revision = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Revisión de Riesgo"
        verbose_name_plural = "Revisiones de Riesgo"
        ordering = ['-fecha_revision']

    def __str__(self):
        return (
            f"Revisión {self.riesgo.codigo} - "
            f"P:{self.probabilidad_anterior}→{self.probabilidad_nueva} "
            f"I:{self.impacto_anterior}→{self.impacto_nueva}"
        )

class RiesgoHistorial(models.Model):
    """
    Registro inmutable de todos los cambios realizados a un Riesgo (audit trail).
    Los registros no pueden ser modificados ni eliminados una vez creados,
    garantizando la trazabilidad completa según ISO 31000:2018.
    """
    TIPO_EVENTO_CHOICES = [
        ('CREACION', 'Creación'),
        ('EVALUACION', 'Evaluación'),
        ('TRATAMIENTO', 'Cambio de tratamiento'),
        ('REVISION', 'Revisión periódica'),
        ('ESTADO', 'Cambio de estado'),
        ('KPI_VINCULADO', 'KPI vinculado'),
        ('KPI_DESVINCULADO', 'KPI desvinculado'),
    ]

    riesgo = models.ForeignKey(
        Riesgo, on_delete=models.CASCADE, related_name='historial'
    )
    tipo_evento = models.CharField(max_length=20, choices=TIPO_EVENTO_CHOICES)
    valores_anteriores = models.JSONField(default=dict, blank=True)
    valores_nuevos = models.JSONField(default=dict, blank=True)
    justificacion = models.TextField(blank=True, default='')
    usuario = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historial de Riesgo"
        verbose_name_plural = "Historial de Riesgos"
        ordering = ['-fecha_hora']

    def __str__(self):
        return (
            f"{self.riesgo.codigo} - {self.get_tipo_evento_display()} "
            f"({self.fecha_hora.strftime('%Y-%m-%d %H:%M') if self.fecha_hora else 'pendiente'})"
        )

    def delete(self, *args, **kwargs):
        """Impedir eliminación de registros de historial."""
        raise PermissionError("Los registros de historial no pueden ser eliminados.")

    def save(self, *args, **kwargs):
        """Impedir modificación de registros de historial existentes."""
        if self.pk:
            raise PermissionError("Los registros de historial no pueden ser modificados.")
        super().save(*args, **kwargs)


# =============================================================================
# Signals
# =============================================================================

@receiver(post_save, sender=AccionTratamiento)
def auto_implementar_plan_tratamiento(sender, instance, **kwargs):
    """
    Auto-transición de PlanTratamiento a "IMPLEMENTADO" cuando todas las acciones
    no-canceladas están completadas y existe al menos una acción completada.
    Solo se activa si el plan no está ya en estado IMPLEMENTADO o CANCELADO.
    Requirement 4.6.
    """
    plan = instance.plan

    # No actuar si el plan ya está implementado o cancelado
    if plan.estado in ('IMPLEMENTADO', 'CANCELADO'):
        return

    # Obtener todas las acciones del plan
    acciones = plan.acciones.all()

    # Filtrar acciones no-canceladas
    acciones_no_canceladas = acciones.exclude(estado='CANCELADA')

    # Debe haber al menos una acción no-cancelada
    if not acciones_no_canceladas.exists():
        return

    # Verificar que al menos una acción esté completada
    tiene_completada = acciones_no_canceladas.filter(estado='COMPLETADA').exists()
    if not tiene_completada:
        return

    # Verificar que TODAS las acciones no-canceladas estén completadas
    todas_completadas = not acciones_no_canceladas.exclude(estado='COMPLETADA').exists()

    if todas_completadas:
        plan.estado = 'IMPLEMENTADO'
        plan.save(update_fields=['estado'])


@receiver(post_save, sender=EvaluacionRiesgo)
def actualizar_estado_apetito_on_evaluacion_residual(sender, instance, **kwargs):
    """
    Cuando se guarda una EvaluacionRiesgo de tipo RESIDUAL, recalcula el
    estado_apetito del Riesgo asociado comparando el nivel_riesgo residual
    contra los umbrales de apetito y tolerancia del Servicio.
    Requirements: 3.3, 3.4, 3.5.
    """
    if instance.tipo == 'RESIDUAL':
        instance.riesgo.actualizar_estado_apetito()


@receiver(post_save, sender=ConfiguracionRiesgoServicio)
def recalcular_estados_on_config_change(sender, instance, **kwargs):
    """
    Cuando se modifica la ConfiguracionRiesgoServicio (apetito o tolerancia),
    recalcula el estado_apetito de todos los riesgos activos del Servicio
    conforme a los nuevos umbrales.
    Requirement 3.7.
    """
    instance.recalcular_estados_riesgos()


@receiver(post_save, sender=RevisionRiesgo)
def actualizar_revision_on_revision_completada(sender, instance, created, **kwargs):
    """
    Cuando se crea una RevisionRiesgo (revisión completada), actualiza la
    próxima fecha de revisión del Riesgo sumando los días del ciclo configurado,
    y recalcula el estado de revisión.
    Requirements: 5.4, 5.5.
    """
    if not created:
        return
    riesgo = instance.riesgo
    # Usar la fecha de la revisión (solo date) o date.today() si no está disponible
    if instance.fecha_revision:
        fecha_completada = instance.fecha_revision.date()
    else:
        fecha_completada = date.today()
    riesgo.actualizar_proxima_revision(fecha_completada)
    riesgo.actualizar_estado_revision()


@receiver(m2m_changed, sender=Riesgo.kpis.through)
def validar_kpi_mismo_servicio(sender, instance, action, pk_set, **kwargs):
    """
    Valida al vincular KPIs a un Riesgo que:
    1. Cada KPI pertenezca al mismo Servicio que el Riesgo.
    2. El total de KPIs vinculados no exceda 20.
    Requirements: 1.4, 7.1, 7.2.
    """
    if action != 'pre_add':
        return

    if not pk_set:
        return

    # Lazy import to avoid circular imports
    from servicios.models import KPI

    # Validación 1: KPIs deben pertenecer al mismo Servicio
    kpis_otro_servicio = KPI.objects.filter(
        pk__in=pk_set
    ).exclude(servicio=instance.servicio)

    if kpis_otro_servicio.exists():
        raise ValidationError(
            "Solo se pueden vincular KPIs del mismo Servicio."
        )

    # Validación 2: Máximo 20 KPIs por Riesgo
    cantidad_actual = instance.kpis.count()
    cantidad_nueva = len(pk_set)

    if cantidad_actual + cantidad_nueva > 20:
        raise ValidationError(
            "Un riesgo no puede tener más de 20 KPIs vinculados."
        )


@receiver(post_save, sender=EvaluacionRiesgo)
def registrar_historial_evaluacion(sender, instance, created, **kwargs):
    """
    Al crear una EvaluacionRiesgo, registra un RiesgoHistorial con tipo_evento='EVALUACION'.
    Registra los valores de la evaluación (tipo, probabilidad, impacto, nivel_riesgo, zona_riesgo).
    Requirements: 6.1.
    """
    if not created:
        return

    RiesgoHistorial.objects.create(
        riesgo=instance.riesgo,
        tipo_evento='EVALUACION',
        valores_nuevos={
            'tipo': instance.tipo,
            'probabilidad': instance.probabilidad,
            'impacto': instance.impacto,
            'nivel_riesgo': instance.nivel_riesgo,
            'zona_riesgo': instance.zona_riesgo,
        },
        usuario=instance.evaluado_por,
    )


@receiver(post_save, sender=AccionTratamiento)
def registrar_historial_tratamiento(sender, instance, created, **kwargs):
    """
    Al guardar una AccionTratamiento (creación o actualización), registra un
    RiesgoHistorial con tipo_evento='TRATAMIENTO'.
    Almacena la información de la acción y su estado actual.
    Requirements: 6.2.
    """
    riesgo = instance.plan.riesgo

    if created:
        RiesgoHistorial.objects.create(
            riesgo=riesgo,
            tipo_evento='TRATAMIENTO',
            valores_nuevos={
                'accion_id': instance.pk,
                'descripcion': instance.descripcion,
                'estado': instance.estado,
            },
            usuario=instance.responsable,
        )
    else:
        # On update, log state change
        RiesgoHistorial.objects.create(
            riesgo=riesgo,
            tipo_evento='TRATAMIENTO',
            valores_anteriores={
                'accion_id': instance.pk,
                'descripcion': instance.descripcion,
            },
            valores_nuevos={
                'accion_id': instance.pk,
                'descripcion': instance.descripcion,
                'estado': instance.estado,
            },
            usuario=instance.responsable,
        )


@receiver(post_save, sender=RevisionRiesgo)
def registrar_historial_revision(sender, instance, created, **kwargs):
    """
    Al crear una RevisionRiesgo (revisión completada), registra un RiesgoHistorial
    con tipo_evento='REVISION' incluyendo valores anteriores y nuevos de la revisión.
    Requirements: 6.2.
    """
    if not created:
        return

    RiesgoHistorial.objects.create(
        riesgo=instance.riesgo,
        tipo_evento='REVISION',
        valores_nuevos={
            'probabilidad_anterior': instance.probabilidad_anterior,
            'impacto_anterior': instance.impacto_anterior,
            'probabilidad_nueva': instance.probabilidad_nueva,
            'impacto_nueva': instance.impacto_nueva,
            'justificacion': instance.justificacion,
        },
        usuario=instance.revisado_por,
    )


@receiver(pre_delete, sender='servicios.KPI')
def registrar_desvinculacion_kpi(sender, instance, **kwargs):
    """
    Antes de eliminar un KPI, registra en el historial de cada Riesgo asociado
    que el KPI fue desvinculado por eliminación.
    Requirements: 7.7.
    """
    # instance is the KPI being deleted
    riesgos_asociados = instance.riesgos_asociados.all()

    for riesgo in riesgos_asociados:
        RiesgoHistorial.objects.create(
            riesgo=riesgo,
            tipo_evento='KPI_DESVINCULADO',
            valores_anteriores={
                'kpi_id': instance.pk,
                'kpi_nombre': instance.nombre,
            },
        )


@receiver(pre_save, sender='servicios.KPI')
def track_kpi_estado_anterior(sender, instance, **kwargs):
    """
    Almacena el estado anterior del KPI antes de guardar para poder
    compararlo en el signal post_save y detectar cambios de estado.
    Requirement 7.3.
    """
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._estado_anterior = old_instance.estado
        except sender.DoesNotExist:
            instance._estado_anterior = None
    else:
        instance._estado_anterior = None


@receiver(post_save, sender='servicios.KPI')
def alerta_kpi_incumplimiento(sender, instance, created, **kwargs):
    """
    Cuando un KPI cambia su estado de CUMPLIMIENTO o PARCIAL a INCUMPLIMIENTO,
    genera una alerta en el historial de cada Riesgo activo asociado, indicando
    posible materialización del riesgo.
    Requirement 7.3.
    """
    if created:
        return

    estado_anterior = getattr(instance, '_estado_anterior', None)

    # Solo actuar si hubo un cambio real a INCUMPLIMIENTO desde CUMPLIMIENTO o PARCIAL
    if (estado_anterior in ('CUMPLIMIENTO', 'PARCIAL') and
            instance.estado == 'INCUMPLIMIENTO'):
        riesgos = instance.riesgos_asociados.filter(estado='ACTIVO')
        for riesgo in riesgos:
            RiesgoHistorial.objects.create(
                riesgo=riesgo,
                tipo_evento='KPI_VINCULADO',
                valores_anteriores={
                    'kpi_id': instance.pk,
                    'kpi_nombre': instance.nombre,
                    'estado_anterior': estado_anterior,
                },
                valores_nuevos={
                    'kpi_id': instance.pk,
                    'kpi_nombre': instance.nombre,
                    'estado_nuevo': 'INCUMPLIMIENTO',
                    'alerta': 'KPI cambió a INCUMPLIMIENTO - posible materialización del riesgo',
                },
            )
