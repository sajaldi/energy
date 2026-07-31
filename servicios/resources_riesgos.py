from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

from .models_riesgos import (
    Riesgo,
    EvaluacionRiesgo,
    PlanTratamiento,
    RevisionRiesgo,
)
from .models import Servicio


class RiesgoResource(resources.ModelResource):
    """
    Resource para exportación Excel del registro de riesgos.
    Columnas según Requirement 10.1:
      código, título, categoría, probabilidad (residual), impacto (residual),
      nivel_riesgo (residual), zona_riesgo (residual), responsable,
      estado_plan_tratamiento, estado, fecha_ultima_revision.
    """

    codigo = fields.Field(attribute='codigo', column_name='Código')
    titulo = fields.Field(attribute='titulo', column_name='Título')
    categoria = fields.Field(column_name='Categoría')
    probabilidad = fields.Field(column_name='Probabilidad (Residual)')
    impacto = fields.Field(column_name='Impacto (Residual)')
    nivel_riesgo = fields.Field(column_name='Nivel de Riesgo (Residual)')
    zona_riesgo = fields.Field(column_name='Zona de Riesgo (Residual)')
    responsable = fields.Field(column_name='Responsable')
    estado_plan_tratamiento = fields.Field(column_name='Estado Plan Tratamiento')
    estado = fields.Field(column_name='Estado')
    fecha_ultima_revision = fields.Field(column_name='Fecha Última Revisión')

    class Meta:
        model = Riesgo
        fields = (
            'codigo',
            'titulo',
            'categoria',
            'probabilidad',
            'impacto',
            'nivel_riesgo',
            'zona_riesgo',
            'responsable',
            'estado_plan_tratamiento',
            'estado',
            'fecha_ultima_revision',
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True

    def dehydrate_categoria(self, riesgo):
        """Retorna el display legible de la categoría."""
        return riesgo.get_categoria_display()

    def dehydrate_probabilidad(self, riesgo):
        """Probabilidad de la última evaluación RESIDUAL."""
        eval_residual = self._get_ultima_evaluacion_residual(riesgo)
        return eval_residual.probabilidad if eval_residual else ''

    def dehydrate_impacto(self, riesgo):
        """Impacto de la última evaluación RESIDUAL."""
        eval_residual = self._get_ultima_evaluacion_residual(riesgo)
        return eval_residual.impacto if eval_residual else ''

    def dehydrate_nivel_riesgo(self, riesgo):
        """Nivel de riesgo (P×I) de la última evaluación RESIDUAL."""
        eval_residual = self._get_ultima_evaluacion_residual(riesgo)
        return eval_residual.nivel_riesgo if eval_residual else ''

    def dehydrate_zona_riesgo(self, riesgo):
        """Zona de riesgo de la última evaluación RESIDUAL (display legible)."""
        eval_residual = self._get_ultima_evaluacion_residual(riesgo)
        if eval_residual:
            return eval_residual.get_zona_riesgo_display()
        return ''

    def dehydrate_responsable(self, riesgo):
        """Nombre completo del responsable del riesgo."""
        if riesgo.responsable:
            full_name = riesgo.responsable.get_full_name()
            return full_name if full_name.strip() else riesgo.responsable.username
        return ''

    def dehydrate_estado_plan_tratamiento(self, riesgo):
        """Estado del PlanTratamiento asociado, o 'Sin plan' si no existe."""
        try:
            plan = riesgo.plan_tratamiento
            return plan.get_estado_display()
        except PlanTratamiento.DoesNotExist:
            return 'Sin plan'

    def dehydrate_estado(self, riesgo):
        """Estado del riesgo en formato legible (Activo/Cerrado)."""
        return riesgo.get_estado_display()

    def dehydrate_fecha_ultima_revision(self, riesgo):
        """Fecha de la última RevisionRiesgo completada."""
        ultima_revision = (
            riesgo.revisiones.order_by('-fecha_revision').first()
        )
        if ultima_revision and ultima_revision.fecha_revision:
            return ultima_revision.fecha_revision.strftime('%Y-%m-%d')
        return ''

    def _get_ultima_evaluacion_residual(self, riesgo):
        """Helper para obtener la última evaluación RESIDUAL del riesgo."""
        if not hasattr(riesgo, '_cached_eval_residual'):
            riesgo._cached_eval_residual = (
                riesgo.evaluaciones
                .filter(tipo='RESIDUAL')
                .order_by('-fecha_evaluacion')
                .first()
            )
        return riesgo._cached_eval_residual


class PlanTratamientoResource(resources.ModelResource):
    """
    Resource para exportación Excel de planes de tratamiento.
    Campos básicos: riesgo (código), estrategia, estado, responsable, fecha_inicio, fecha_limite.
    """

    riesgo__codigo = fields.Field(
        column_name='Código Riesgo',
        attribute='riesgo__codigo',
    )
    estrategia = fields.Field(column_name='Estrategia')
    estado = fields.Field(column_name='Estado')
    responsable__username = fields.Field(column_name='Responsable')
    fecha_inicio = fields.Field(attribute='fecha_inicio', column_name='Fecha Inicio')
    fecha_limite = fields.Field(attribute='fecha_limite', column_name='Fecha Límite')

    class Meta:
        model = PlanTratamiento
        fields = (
            'riesgo__codigo',
            'estrategia',
            'estado',
            'responsable__username',
            'fecha_inicio',
            'fecha_limite',
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True

    def dehydrate_riesgo__codigo(self, plan):
        """Código del riesgo asociado al plan."""
        return plan.riesgo.codigo if plan.riesgo else ''

    def dehydrate_estrategia(self, plan):
        """Estrategia en formato legible."""
        return plan.get_estrategia_display()

    def dehydrate_estado(self, plan):
        """Estado del plan en formato legible."""
        return plan.get_estado_display()

    def dehydrate_responsable__username(self, plan):
        """Username del responsable del plan."""
        if plan.responsable:
            return plan.responsable.username
        return ''
