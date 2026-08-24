"""
Dashboard Energetico - Vista principal de consumo energetico.
Calcula consumos respetando la logica PUNTUAL vs ACUMULATIVO.
"""
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from core.models import Medidor, Consumo


def calcular_consumo_periodo(medidor, fecha_desde, fecha_hasta):
    """
    Calcula el consumo de un medidor en un periodo dado.
    - PUNTUAL: SUM(consumo) en el periodo
    - ACUMULATIVO: ultima_lectura - primera_lectura del periodo
    """
    qs = Consumo.objects.filter(
        medidor=medidor,
        fecha__gte=fecha_desde,
        fecha__lte=fecha_hasta
    )

    tipo = (medidor.tipo or '').strip().upper()

    if tipo == 'PUNTUAL':
        result = qs.aggregate(total=Sum('consumo'))
        return result['total'] or 0
    else:
        # ACUMULATIVO: last - first
        primera = qs.order_by('fecha').first()
        ultima = qs.order_by('-fecha').first()
        if primera and ultima and primera.pk != ultima.pk:
            return (ultima.consumo or 0) - (primera.consumo or 0)
        return 0


def _calcular_consumo_medidores_periodo(medidores, fecha_desde, fecha_hasta):
    """
    Calcula el consumo total de una lista de medidores en un periodo,
    optimizado para reducir queries.
    Retorna dict {medidor_id: consumo} y el total.
    """
    resultado = {}
    total = 0

    # Separar medidores por tipo
    puntuales = [m for m in medidores if (m.tipo or '').strip().upper() == 'PUNTUAL']
    acumulativos = [m for m in medidores if (m.tipo or '').strip().upper() != 'PUNTUAL']

    # PUNTUAL: una sola query agregada
    if puntuales:
        ids_puntuales = [m.id for m in puntuales]
        agg = (
            Consumo.objects.filter(
                medidor_id__in=ids_puntuales,
                fecha__gte=fecha_desde,
                fecha__lte=fecha_hasta
            )
            .values('medidor_id')
            .annotate(total=Sum('consumo'))
        )
        for row in agg:
            val = row['total'] or 0
            resultado[row['medidor_id']] = val
            total += val

    # ACUMULATIVO: necesitamos primera y ultima lectura por medidor
    for m in acumulativos:
        val = calcular_consumo_periodo(m, fecha_desde, fecha_hasta)
        resultado[m.id] = val
        total += val

    return resultado, total


@staff_member_required
def dashboard_energia(request):
    """Vista principal del Dashboard Energetico."""
    now = timezone.now()

    # --- Filtros ---
    medidor_id = request.GET.get('medidor_id')
    fecha_desde_str = request.GET.get('fecha_desde')
    fecha_hasta_str = request.GET.get('fecha_hasta')

    # Determinar periodo actual
    if fecha_desde_str:
        try:
            fecha_desde_mes = timezone.make_aware(
                datetime.strptime(fecha_desde_str, '%Y-%m-%d')
            )
        except (ValueError, TypeError):
            fecha_desde_mes = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        fecha_desde_mes = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if fecha_hasta_str:
        try:
            fecha_hasta_mes = timezone.make_aware(
                datetime.strptime(fecha_hasta_str, '%Y-%m-%d').replace(
                    hour=23, minute=59, second=59
                )
            )
        except (ValueError, TypeError):
            fecha_hasta_mes = now
    else:
        fecha_hasta_mes = now

    # Periodo anterior (mismo rango de dias, mes anterior)
    delta_dias = (fecha_hasta_mes - fecha_desde_mes).days
    fecha_hasta_anterior = fecha_desde_mes - timedelta(seconds=1)
    fecha_desde_anterior = fecha_hasta_anterior - timedelta(days=delta_dias)

    # --- Medidores ---
    medidores_qs = Medidor.objects.select_related('unidad', 'tipo_medidor').all()
    if medidor_id:
        try:
            medidores_qs = medidores_qs.filter(id=int(medidor_id))
        except (ValueError, TypeError):
            pass

    medidores = list(medidores_qs)
    total_medidores = len(medidores)

    # --- KPIs: Consumo total mes actual y anterior ---
    consumos_actual, consumo_total_mes = _calcular_consumo_medidores_periodo(
        medidores, fecha_desde_mes, fecha_hasta_mes
    )
    _, consumo_total_anterior = _calcular_consumo_medidores_periodo(
        medidores, fecha_desde_anterior, fecha_hasta_anterior
    )

    # Variacion porcentual
    if consumo_total_anterior > 0:
        variacion_pct = round(
            ((consumo_total_mes - consumo_total_anterior) / consumo_total_anterior) * 100, 1
        )
    else:
        variacion_pct = 0 if consumo_total_mes == 0 else 100.0

    # --- Top 10 consumidores ---
    top_consumidores = sorted(
        [
            {
                'nombre': m.nombre,
                'consumo': round(consumos_actual.get(m.id, 0), 2),
                'unidad': m.unidad.simbolo if m.unidad else '',
                'tipo': (m.tipo or '').strip().upper() or 'ACUMULATIVO',
            }
            for m in medidores
        ],
        key=lambda x: x['consumo'],
        reverse=True
    )[:10]

    # --- Tendencia mensual (12 meses) ---
    tendencia_mensual = []
    meses_labels = []
    for i in range(11, -1, -1):
        mes_ref = now - relativedelta(months=i)
        inicio_mes = mes_ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i == 0:
            fin_mes = now
        else:
            fin_mes = (inicio_mes + relativedelta(months=1)) - timedelta(seconds=1)

        _, total_mes = _calcular_consumo_medidores_periodo(medidores, inicio_mes, fin_mes)
        tendencia_mensual.append(round(total_mes, 2))
        meses_labels.append(inicio_mes.strftime('%b %Y'))

    # --- Consumo diario del mes actual ---
    consumo_diario = []
    dias_labels = []
    dia_inicio = fecha_desde_mes
    while dia_inicio.date() <= fecha_hasta_mes.date():
        dia_fin = dia_inicio.replace(hour=23, minute=59, second=59)

        # Para consumo diario usamos query directa optimizada
        if medidor_id:
            filtro_medidor = Q(medidor_id=int(medidor_id))
        else:
            filtro_medidor = Q()

        # Para PUNTUAL sumamos directamente, para ACUMULATIVO necesitamos logica especial
        # Optimizacion: si todos son del mismo tipo, hacemos una sola query
        # Caso general: calculamos por medidor (puede ser lento con muchos medidores)
        total_dia = 0
        puntuales_ids = [m.id for m in medidores if (m.tipo or '').strip().upper() == 'PUNTUAL']
        acumulativos_list = [m for m in medidores if (m.tipo or '').strip().upper() != 'PUNTUAL']

        if puntuales_ids:
            agg = Consumo.objects.filter(
                medidor_id__in=puntuales_ids,
                fecha__gte=dia_inicio,
                fecha__lte=dia_fin
            ).aggregate(total=Sum('consumo'))
            total_dia += agg['total'] or 0

        for m in acumulativos_list:
            total_dia += calcular_consumo_periodo(m, dia_inicio, dia_fin)

        consumo_diario.append(round(total_dia, 2))
        dias_labels.append(dia_inicio.strftime('%d'))
        dia_inicio += timedelta(days=1)

    # --- Distribucion por medidor (top 8 + Otros) ---
    distribucion_data = sorted(
        [
            {'nombre': m.nombre, 'consumo': round(consumos_actual.get(m.id, 0), 2)}
            for m in medidores
        ],
        key=lambda x: x['consumo'],
        reverse=True
    )

    dist_labels = []
    dist_values = []
    if len(distribucion_data) > 8:
        for item in distribucion_data[:8]:
            dist_labels.append(item['nombre'])
            dist_values.append(item['consumo'])
        otros_total = sum(item['consumo'] for item in distribucion_data[8:])
        dist_labels.append('Otros')
        dist_values.append(round(otros_total, 2))
    else:
        for item in distribucion_data:
            dist_labels.append(item['nombre'])
            dist_values.append(item['consumo'])

    # --- Tabla de medidores con tendencia ---
    tabla_medidores = []
    for m in medidores:
        consumo_act = consumos_actual.get(m.id, 0)
        consumo_ant = calcular_consumo_periodo(m, fecha_desde_anterior, fecha_hasta_anterior)
        if consumo_ant > 0:
            tendencia = 'up' if consumo_act > consumo_ant else 'down'
        elif consumo_act > 0:
            tendencia = 'up'
        else:
            tendencia = 'neutral'

        tabla_medidores.append({
            'nombre': m.nombre,
            'consumo': round(consumo_act, 2),
            'unidad': m.unidad.simbolo if m.unidad else '',
            'tipo': (m.tipo or '').strip().upper() or 'ACUMULATIVO',
            'tendencia': tendencia,
        })

    # Ordenar tabla por consumo descendente
    tabla_medidores.sort(key=lambda x: x['consumo'], reverse=True)

    # --- Lista de medidores para filtro ---
    todos_medidores = Medidor.objects.all().order_by('nombre')

    context = {
        'consumo_total_mes': round(consumo_total_mes, 2),
        'variacion_pct': variacion_pct,
        'total_medidores': total_medidores,
        'top_consumidores': top_consumidores,
        'tabla_medidores': tabla_medidores,
        # JSON para Chart.js
        'tendencia_labels_json': json.dumps(meses_labels),
        'tendencia_data_json': json.dumps(tendencia_mensual),
        'diario_labels_json': json.dumps(dias_labels),
        'diario_data_json': json.dumps(consumo_diario),
        'dist_labels_json': json.dumps(dist_labels),
        'dist_data_json': json.dumps(dist_values),
        # Filtros
        'medidor_id_selected': medidor_id or '',
        'fecha_desde': fecha_desde_str or fecha_desde_mes.strftime('%Y-%m-%d'),
        'fecha_hasta': fecha_hasta_str or fecha_hasta_mes.strftime('%Y-%m-%d'),
        'todos_medidores': todos_medidores,
    }

    return render(request, 'core/dashboard_energia.html', context)


# ============================================================
# DASHBOARD TV MEDIDORES
# ============================================================

def medidores_tv_dashboard(request):
    """Dashboard TV de medidores (público, sin login)."""
    from .models import DashboardMedidorConfig
    config = DashboardMedidorConfig.get_active()
    return render(request, 'core/medidores_tv_dashboard.html', {
        'config': config,
        'title': config.titulo,
    })


def medidores_tv_api(request):
    """API JSON para el dashboard TV de medidores."""
    from .models import DashboardMedidorConfig, Medidor, Consumo
    from django.db.models import Max
    from django.utils import timezone as tz
    from datetime import timedelta

    config = DashboardMedidorConfig.get_active()
    medidores = config.medidores.all().select_related('unidad', 'tipo_medidor')

    if not medidores.exists():
        medidores = Medidor.objects.all().select_related('unidad', 'tipo_medidor')

    now = tz.now()
    resultados = []

    for m in medidores:
        # Último consumo
        ultimo = Consumo.objects.filter(medidor=m).order_by('-fecha').first()
        # Consumo de hace 24h para comparar
        hace_24h = now - timedelta(hours=24)
        anterior = Consumo.objects.filter(medidor=m, fecha__lte=hace_24h).order_by('-fecha').first()

        valor_actual = ultimo.consumo if ultimo else 0
        valor_anterior = anterior.consumo if anterior else 0

        if m.tipo and m.tipo.strip().upper() == 'PUNTUAL':
            # Puntual: valor directo
            display = valor_actual
        else:
            # Acumulativo: diferencia
            display = valor_actual - valor_anterior if valor_anterior else valor_actual

        resultados.append({
            'id': m.id,
            'nombre': m.nombre,
            'valor': round(display, 2),
            'unidad': m.unidad.simbolo if m.unidad else '',
            'tipo': m.tipo_medidor.nombre if m.tipo_medidor else (m.tipo or '-'),
            'ultima_lectura': ultimo.fecha.strftime('%d/%m/%Y %H:%M') if ultimo else '-',
        })

    data = {
        'titulo': config.titulo,
        'intervalo_refresh': config.intervalo_refresh,
        'medidores': resultados,
        'total_medidores': len(resultados),
        'timestamp': now.isoformat(),
    }
    return JsonResponse(data)


@staff_member_required
def medidores_dashboard_config(request):
    """Configurador del dashboard TV de medidores."""
    from .models import DashboardMedidorConfig, Medidor
    from django.contrib import messages
    from django.shortcuts import redirect

    config = DashboardMedidorConfig.get_active()

    if request.method == 'POST':
        config.titulo = request.POST.get('titulo', config.titulo)
        config.intervalo_refresh = int(request.POST.get('intervalo_refresh', 60))
        config.save()
        medidor_ids = request.POST.getlist('medidores')
        config.medidores.set(medidor_ids)
        messages.success(request, 'Configuración guardada correctamente.')
        return redirect('core:medidores_dashboard_config')

    medidores_todos = Medidor.objects.all().order_by('nombre')
    selected_ids = list(config.medidores.values_list('id', flat=True))

    return render(request, 'core/medidores_dashboard_config.html', {
        'config': config,
        'medidores_todos': medidores_todos,
        'selected_ids': selected_ids,
        'title': 'Configuración Dashboard Medidores',
    })
