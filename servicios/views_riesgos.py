"""
Vistas del módulo de Análisis de Riesgos de Negocio.
Panel de riesgos, mapa de calor, historial y exportaciones.
"""
import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Subquery, OuterRef
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import KPI, Servicio
from .models_riesgos import (
    AccionTratamiento,
    EvaluacionRiesgo,
    PlanTratamiento,
    Riesgo,
    RiesgoHistorial,
)


@login_required
def panel_riesgos_view(request):
    """
    Dashboard consolidado de riesgos (Panel_Riesgos).
    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.7
    """
    # --- Filtros (Req 9.4) ---
    servicio_id = request.GET.get('servicio')
    categoria = request.GET.get('categoria')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    # Base queryset: riesgos activos
    riesgos = Riesgo.objects.filter(estado='ACTIVO')

    # Filtro por Servicio
    if servicio_id:
        riesgos = riesgos.filter(servicio_id=servicio_id)

    # Filtro por Categoría
    if categoria:
        riesgos = riesgos.filter(categoria=categoria)

    # Filtro por período (default: últimos 12 meses) - Req 9.5
    if fecha_inicio and fecha_fin:
        riesgos = riesgos.filter(
            fecha_identificacion__date__gte=fecha_inicio,
            fecha_identificacion__date__lte=fecha_fin,
        )
    else:
        fecha_default = timezone.now() - timedelta(days=365)
        riesgos = riesgos.filter(fecha_identificacion__gte=fecha_default)

    # --- Indicadores consolidados (Req 9.1) ---
    total_activos = riesgos.count()

    # Distribución por Zona de Riesgo (basada en última evaluación RESIDUAL)
    ultima_eval_residual_zona = (
        EvaluacionRiesgo.objects
        .filter(riesgo=OuterRef('pk'), tipo='RESIDUAL')
        .order_by('-fecha_evaluacion')
        .values('zona_riesgo')[:1]
    )

    riesgos_con_zona = riesgos.annotate(
        zona_residual=Subquery(ultima_eval_residual_zona)
    )

    distribucion_zona = {'BAJO': 0, 'MEDIO': 0, 'ALTO': 0, 'CRITICO': 0}
    for r in riesgos_con_zona:
        zona = r.zona_residual or 'BAJO'
        distribucion_zona[zona] = distribucion_zona.get(zona, 0) + 1

    distribucion_zona_pct = {
        k: round(v / total_activos * 100, 1) if total_activos > 0 else 0
        for k, v in distribucion_zona.items()
    }

    # Distribución por Categoría
    distribucion_categoria = {}
    for choice_val, choice_label in Riesgo.CATEGORIA_CHOICES:
        count = riesgos.filter(categoria=choice_val).count()
        if count > 0:
            distribucion_categoria[choice_label] = count

    distribucion_categoria_pct = {
        k: round(v / total_activos * 100, 1) if total_activos > 0 else 0
        for k, v in distribucion_categoria.items()
    }

    # % Planes de tratamiento implementados
    planes_qs = PlanTratamiento.objects.all()
    if servicio_id:
        planes_qs = planes_qs.filter(riesgo__servicio_id=servicio_id)
    total_planes = planes_qs.count()
    planes_implementados = planes_qs.filter(estado='IMPLEMENTADO').count()
    pct_implementados = round(
        (planes_implementados / total_planes * 100) if total_planes > 0 else 0, 1
    )

    # --- Top 10 riesgos por nivel_riesgo residual descendente (Req 9.2) ---
    ultima_eval_residual_nivel = (
        EvaluacionRiesgo.objects
        .filter(riesgo=OuterRef('pk'), tipo='RESIDUAL')
        .order_by('-fecha_evaluacion')
        .values('nivel_riesgo')[:1]
    )

    top_riesgos = (
        riesgos
        .annotate(nivel_residual=Subquery(ultima_eval_residual_nivel))
        .filter(nivel_residual__isnull=False)
        .order_by('-nivel_residual')[:10]
    )

    # --- Revisiones vencidas (hasta 20, por antigüedad) (Req 9.3) ---
    revisiones_vencidas = (
        riesgos
        .filter(estado_revision='VENCIDA')
        .order_by('proxima_revision')[:20]
    )

    # --- Acciones vencidas (hasta 20, por antigüedad) (Req 9.3) ---
    acciones_vencidas_qs = AccionTratamiento.objects.filter(
        estado__in=['PENDIENTE', 'EN_PROGRESO'],
        fecha_limite__lt=timezone.now().date(),
    ).select_related('plan__riesgo')

    if servicio_id:
        acciones_vencidas_qs = acciones_vencidas_qs.filter(
            plan__riesgo__servicio_id=servicio_id
        )

    acciones_vencidas = acciones_vencidas_qs.order_by('fecha_limite')[:20]

    # --- KPIs en riesgo (Req 7.6) ---
    # KPIs en INCUMPLIMIENTO/PARCIAL con riesgos asociados en zona Alta/Crítica
    kpis_en_riesgo = (
        KPI.objects
        .filter(
            Q(estado='INCUMPLIMIENTO') | Q(estado='PARCIAL'),
            riesgos_asociados__estado='ACTIVO',
        )
        .distinct()[:10]
    )

    # --- Opciones para filtros del template ---
    servicios = Servicio.objects.filter(activo=True).order_by('nombre')
    categorias = Riesgo.CATEGORIA_CHOICES

    # --- Mensaje sin resultados (Req 9.7) ---
    sin_resultados = total_activos == 0

    context = {
        # Indicadores
        'total_activos': total_activos,
        'distribucion_zona': distribucion_zona,
        'distribucion_zona_pct': distribucion_zona_pct,
        'distribucion_categoria': distribucion_categoria,
        'distribucion_categoria_pct': distribucion_categoria_pct,
        'pct_implementados': pct_implementados,
        'total_planes': total_planes,
        'planes_implementados': planes_implementados,
        # Listados
        'top_riesgos': top_riesgos,
        'revisiones_vencidas': revisiones_vencidas,
        'acciones_vencidas': acciones_vencidas,
        'kpis_en_riesgo': kpis_en_riesgo,
        # Filtros
        'servicios': servicios,
        'categorias': categorias,
        'filtro_servicio': servicio_id,
        'filtro_categoria': categoria,
        'filtro_fecha_inicio': fecha_inicio,
        'filtro_fecha_fin': fecha_fin,
        # Estado
        'sin_resultados': sin_resultados,
    }
    return render(request, 'servicios/riesgos/panel_riesgos.html', context)


@login_required
def mapa_calor_view(request, servicio_id):
    """
    Mapa de calor 5×5 para un Servicio específico.
    Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 3.6
    """
    from .models_riesgos import ConfiguracionRiesgoServicio

    servicio = get_object_or_404(Servicio, pk=servicio_id)
    riesgos_activos = Riesgo.objects.filter(
        servicio=servicio, estado='ACTIVO'
    ).prefetch_related('evaluaciones')

    # Get view mode from query param: 'inherente', 'residual', 'ambos' (Req 8.8)
    vista = request.GET.get('vista', 'ambos')
    if vista not in ('inherente', 'residual', 'ambos'):
        vista = 'ambos'

    # Build grid data: 5×5 matrix keyed by (probabilidad, impacto)
    grid = {}
    for p in range(1, 6):
        for i in range(1, 6):
            grid[(p, i)] = {'inherente': [], 'residual': []}

    for riesgo in riesgos_activos:
        eval_inh = (
            riesgo.evaluaciones
            .filter(tipo='INHERENTE')
            .order_by('-fecha_evaluacion')
            .first()
        )
        eval_res = (
            riesgo.evaluaciones
            .filter(tipo='RESIDUAL')
            .order_by('-fecha_evaluacion')
            .first()
        )

        if eval_inh:
            cell = grid[(eval_inh.probabilidad, eval_inh.impacto)]
            cell['inherente'].append(riesgo)
        if eval_res:
            cell = grid[(eval_res.probabilidad, eval_res.impacto)]
            cell['residual'].append(riesgo)

    # Prepare grid for template (list format, Y axis 5→1 top to bottom)
    grid_data = []
    for p in range(5, 0, -1):
        row = []
        for i in range(1, 6):
            nivel = p * i
            zona = _clasificar_zona(nivel)

            cell_data = grid[(p, i)]
            riesgos_inh = cell_data['inherente'][:10]
            riesgos_res = cell_data['residual'][:10]
            total_inh = len(cell_data['inherente'])
            total_res = len(cell_data['residual'])

            row.append({
                'prob': p,
                'imp': i,
                'nivel': nivel,
                'zona': zona,
                'riesgos_inherente': riesgos_inh,
                'riesgos_residual': riesgos_res,
                'total_inherente': total_inh,
                'total_residual': total_res,
                'extra_inherente': max(0, total_inh - 10),
                'extra_residual': max(0, total_res - 10),
            })
        grid_data.append({'prob': p, 'cells': row})

    # Get appetite/tolerance lines for the service (Req 3.6)
    try:
        config = servicio.config_riesgo
        apetito = config.apetito_riesgo
        tolerancia = config.umbral_tolerancia
    except ConfiguracionRiesgoServicio.DoesNotExist:
        apetito = None
        tolerancia = None

    context = {
        'servicio': servicio,
        'grid_data': grid_data,
        'vista': vista,
        'apetito': apetito,
        'tolerancia': tolerancia,
        'tiene_riesgos': riesgos_activos.exists(),
    }
    return render(request, 'servicios/riesgos/mapa_calor.html', context)


@login_required
def mapa_calor_consolidado_view(request):
    """
    Mapa de calor consolidado de todos los Servicios.
    Muestra conteo de riesgos activos por celda usando evaluación residual.
    Requirement 8.4
    """
    riesgos_activos = Riesgo.objects.filter(
        estado='ACTIVO'
    ).prefetch_related('evaluaciones')

    # Build grid with counts
    grid = {}
    for p in range(1, 6):
        for i in range(1, 6):
            grid[(p, i)] = 0

    for riesgo in riesgos_activos:
        eval_res = (
            riesgo.evaluaciones
            .filter(tipo='RESIDUAL')
            .order_by('-fecha_evaluacion')
            .first()
        )
        if eval_res:
            grid[(eval_res.probabilidad, eval_res.impacto)] += 1

    # Prepare grid for template (same structure as per-service view)
    grid_data = []
    for p in range(5, 0, -1):
        row = []
        for i in range(1, 6):
            nivel = p * i
            zona = _clasificar_zona(nivel)
            row.append({
                'prob': p,
                'imp': i,
                'nivel': nivel,
                'zona': zona,
                'conteo': grid[(p, i)],
            })
        grid_data.append({'prob': p, 'cells': row})

    context = {
        'grid_data': grid_data,
        'consolidado': True,
        'tiene_riesgos': riesgos_activos.exists(),
    }
    return render(request, 'servicios/riesgos/mapa_calor.html', context)


def _clasificar_zona(nivel):
    """
    Clasifica la zona de riesgo según el nivel calculado (P×I).
    - Bajo: 1-4
    - Medio: 5-9
    - Alto: 10-16
    - Crítico: 17-25
    """
    if nivel <= 4:
        return 'BAJO'
    elif nivel <= 9:
        return 'MEDIO'
    elif nivel <= 16:
        return 'ALTO'
    else:
        return 'CRITICO'


@login_required
def historial_riesgo_view(request, riesgo_id):
    """Timeline de historial de un Riesgo con paginación y gráfico de tendencia. Requirements: 6.3, 6.5, 6.6, 6.7"""
    riesgo = get_object_or_404(Riesgo, pk=riesgo_id)

    # Get filter parameters
    tipo_evento = request.GET.get('tipo_evento')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')

    # Base queryset (already ordered by -fecha_hora via Meta)
    historial = riesgo.historial.all()

    # Apply filters
    if tipo_evento:
        historial = historial.filter(tipo_evento=tipo_evento)
    if fecha_desde:
        historial = historial.filter(fecha_hora__date__gte=fecha_desde)
    if fecha_hasta:
        historial = historial.filter(fecha_hora__date__lte=fecha_hasta)

    # Paginate (20 per page) - Requirement 6.3
    paginator = Paginator(historial, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Trend chart data: evaluations with ≥2 data points - Requirements 6.5, 6.6
    evaluaciones = riesgo.evaluaciones.filter(tipo='RESIDUAL').order_by('fecha_evaluacion')
    tiene_suficientes_evaluaciones = evaluaciones.count() >= 2
    chart_data = None
    if tiene_suficientes_evaluaciones:
        chart_data = json.dumps({
            'labels': [e.fecha_evaluacion.strftime('%Y-%m-%d') for e in evaluaciones],
            'values': [e.nivel_riesgo for e in evaluaciones],
        })

    context = {
        'riesgo': riesgo,
        'page_obj': page_obj,
        'chart_data': chart_data,
        'tipo_evento_choices': RiesgoHistorial.TIPO_EVENTO_CHOICES,
        'filtro_tipo_evento': tipo_evento or '',
        'filtro_fecha_desde': fecha_desde or '',
        'filtro_fecha_hasta': fecha_hasta or '',
        'tiene_suficientes_evaluaciones': tiene_suficientes_evaluaciones,
    }
    return render(request, 'servicios/riesgos/historial.html', context)


@login_required
def export_riesgos_excel_view(request):
    """
    Exportar riesgos en formato Excel (.xlsx).

    Lógica sync/async:
    - Si el queryset tiene ≤100 registros, genera el XLSX de forma síncrona
      y lo retorna como descarga directa.
    - Si tiene >100 registros, despacha la tarea Celery
      export_riesgos_excel_task y retorna un JSON informando al usuario.

    Filtros (se mantienen para reintento en caso de error):
    - servicio_id: filtra por Servicio
    - estado_filter: 'ACTIVO', 'CERRADO' o vacío (ambos)

    Requirements: 10.1, 10.4, 10.5, 10.6
    """
    from django.http import JsonResponse

    from .resources_riesgos import RiesgoResource
    from .tasks_riesgos import export_riesgos_excel_task

    # --- Obtener filtros desde GET ---
    servicio_id = request.GET.get('servicio_id') or request.GET.get('servicio')
    estado_filter = request.GET.get('estado_filter', '').upper()

    # Validar estado_filter
    if estado_filter not in ('ACTIVO', 'CERRADO'):
        estado_filter = ''  # Ambos

    # --- Construir queryset filtrado ---
    queryset = Riesgo.objects.select_related(
        'servicio', 'responsable'
    ).prefetch_related(
        'evaluaciones', 'revisiones', 'plan_tratamiento'
    )

    if servicio_id:
        queryset = queryset.filter(servicio_id=servicio_id)

    if estado_filter:
        queryset = queryset.filter(estado=estado_filter)

    queryset = queryset.order_by('-fecha_identificacion')

    count = queryset.count()

    # --- Sync: ≤100 registros ---
    if count <= 100:
        resource = RiesgoResource()
        dataset = resource.export(queryset=queryset)

        response = HttpResponse(
            dataset.xlsx,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="riesgos_export.xlsx"'
        return response

    # --- Async: >100 registros → Celery task ---
    export_riesgos_excel_task.delay(
        servicio_id=servicio_id,
        estado_filter=estado_filter or None,
        user_id=request.user.id,
    )

    return JsonResponse({
        'status': 'processing',
        'message': (
            'La exportación se está procesando. '
            'Recibirá una notificación cuando esté disponible.'
        ),
        'filters': {
            'servicio_id': servicio_id,
            'estado_filter': estado_filter,
        },
    })


@login_required
def export_matriz_pdf_view(request, servicio_id):
    """
    Exportar matriz de riesgos en formato PDF.

    Despacha la tarea Celery export_matriz_pdf_task para la generación
    del PDF (siempre asíncrona, a menos que CELERY_TASK_ALWAYS_EAGER=True
    en cuyo caso se ejecuta de forma síncrona de manera transparente).

    Retorna un JSON informando que la exportación está en proceso.

    Requirements: 10.2, 10.3, 10.5, 10.6
    """
    from django.http import JsonResponse

    from .tasks_riesgos import export_matriz_pdf_task

    # Validar que el servicio existe
    get_object_or_404(Servicio, pk=servicio_id)

    export_matriz_pdf_task.delay(
        servicio_id=servicio_id,
        user_id=request.user.id,
    )

    return JsonResponse({
        'status': 'processing',
        'message': 'La exportación PDF se está procesando.',
        'filters': {
            'servicio_id': servicio_id,
        },
    })


@login_required
def api_crear_riesgo(request):
    """
    API endpoint para crear un Riesgo via AJAX (POST JSON).
    Usado por el modal wizard del panel de riesgos.
    """
    from django.http import JsonResponse
    from django.views.decorators.http import require_POST

    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    # Validar campos obligatorios
    errores = {}
    campos_requeridos = ['servicio_id', 'titulo', 'descripcion', 'categoria', 'fuente_riesgo', 'consecuencias']
    for campo in campos_requeridos:
        if not data.get(campo, '').strip() if isinstance(data.get(campo), str) else not data.get(campo):
            errores[campo] = 'Este campo es obligatorio.'

    if errores:
        return JsonResponse({'errores': errores}, status=400)

    # Validar servicio
    try:
        servicio = Servicio.objects.get(pk=data['servicio_id'])
    except Servicio.DoesNotExist:
        return JsonResponse({'errores': {'servicio_id': 'Servicio no encontrado.'}}, status=400)

    # Validar categoría
    categorias_validas = [c[0] for c in Riesgo.CATEGORIA_CHOICES]
    if data['categoria'] not in categorias_validas:
        return JsonResponse({'errores': {'categoria': 'Categoría no válida.'}}, status=400)

    # Crear el riesgo
    try:
        riesgo = Riesgo(
            servicio=servicio,
            titulo=data['titulo'].strip(),
            descripcion=data['descripcion'].strip(),
            categoria=data['categoria'],
            fuente_riesgo=data['fuente_riesgo'].strip(),
            consecuencias=data['consecuencias'].strip(),
            control_existente=data.get('control_existente', '').strip(),
            creado_por=request.user,
            responsable=request.user,
            ciclo_revision=data.get('ciclo_revision', 'TRIMESTRAL'),
        )
        riesgo.full_clean()
        riesgo.save()

        # Crear evaluación inherente si se proporcionó
        if data.get('probabilidad_inherente') and data.get('impacto_inherente'):
            eval_inh = EvaluacionRiesgo(
                riesgo=riesgo,
                tipo='INHERENTE',
                probabilidad=int(data['probabilidad_inherente']),
                impacto=int(data['impacto_inherente']),
                justificacion_probabilidad=data.get('justificacion_prob_inherente', 'Evaluación inicial').strip() or 'Evaluación inicial',
                justificacion_impacto=data.get('justificacion_imp_inherente', 'Evaluación inicial').strip() or 'Evaluación inicial',
                evaluado_por=request.user,
            )
            eval_inh.full_clean()
            eval_inh.save()

        # Crear evaluación residual si se proporcionó
        if data.get('probabilidad_residual') and data.get('impacto_residual'):
            eval_res = EvaluacionRiesgo(
                riesgo=riesgo,
                tipo='RESIDUAL',
                probabilidad=int(data['probabilidad_residual']),
                impacto=int(data['impacto_residual']),
                justificacion_probabilidad=data.get('justificacion_prob_residual', 'Evaluación inicial').strip() or 'Evaluación inicial',
                justificacion_impacto=data.get('justificacion_imp_residual', 'Evaluación inicial').strip() or 'Evaluación inicial',
                evaluado_por=request.user,
            )
            eval_res.full_clean()
            eval_res.save()

        return JsonResponse({
            'success': True,
            'riesgo': {
                'id': riesgo.pk,
                'codigo': riesgo.codigo,
                'titulo': riesgo.titulo,
                'categoria': riesgo.get_categoria_display(),
                'servicio': servicio.nombre,
            },
            'message': f'Riesgo {riesgo.codigo} creado exitosamente.',
        })

    except Exception as e:
        return JsonResponse({'errores': {'__all__': str(e)}}, status=400)
