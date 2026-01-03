from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from .models import PresupuestoAnual, PartidaPresupuestaria, GastoEjecutado, ItemPresupuesto
from django.contrib.auth.decorators import login_required
from datetime import datetime

@login_required
def presupuesto_matrix(request, pk=None):
    if pk:
        presupuesto = get_object_or_404(PresupuestoAnual, pk=pk)
    else:
        # Por defecto el presupuesto del año actual o el mas reciente
        presupuesto = PresupuestoAnual.objects.filter(anio=datetime.now().year).first()
        if not presupuesto:
            presupuesto = PresupuestoAnual.objects.order_by('-anio').first()
    
    if not presupuesto:
        return render(request, 'presupuestos/presupuesto_matrix.html', {'error': 'No hay presupuestos configurados.'})

    partidas_data = []
    meses_indices = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
    meses_nombres = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

    partidas = presupuesto.partidas.select_related('disciplina').prefetch_related('items', 'gastos').all()

    for p in partidas:
        items_desglose = []
        for item in p.items.all():
            proyeccion_mensual = [
                getattr(item, m) for m in meses_indices
            ]
            items_desglose.append({
                'concepto': item.concepto,
                'proyeccion': proyeccion_mensual,
                'total_anual': item.total_anual
            })
        
        # Consolidar ejecucion real por mes
        ejecucion_mensual = [0] * 12
        for gasto in p.gastos.all():
            m_idx = gasto.fecha.month - 1 # 1-12 to 0-11
            ejecucion_mensual[m_idx] += float(gasto.monto)
        
        # Consolidar proyeccion total de la partida por mes (suma de sus items)
        proyeccion_total_mensual = [0] * 12
        for item in items_desglose:
            for i in range(12):
                proyeccion_total_mensual[i] += float(item['proyeccion'][i])

        partidas_data.append({
            'partida': p,
            'disciplina': p.disciplina.nombre if p.disciplina else "Sin Disciplina",
            'items': items_desglose,
            'ejecucion_mensual': ejecucion_mensual,
            'proyeccion_total_mensual': proyeccion_total_mensual,
            'total_proyectado': sum(proyeccion_total_mensual),
            'total_ejecutado': sum(ejecucion_mensual)
        })

    # Totales globales por mes
    global_proyectado_mes = [0] * 12
    global_ejecutado_mes = [0] * 12
    for pd in partidas_data:
        for i in range(12):
            global_proyectado_mes[i] += pd['proyeccion_total_mensual'][i]
            global_ejecutado_mes[i] += pd['ejecucion_mensual'][i]

    context = {
        'presupuesto': presupuesto,
        'partidas_data': partidas_data,
        'meses_nombres': meses_nombres,
        'global_proyectado_mes': global_proyectado_mes,
        'global_ejecutado_mes': global_ejecutado_mes,
        'total_general_proyectado': sum(global_proyectado_mes),
        'total_general_ejecutado': sum(global_ejecutado_mes),
    }

    return render(request, 'presupuestos/presupuesto_matrix.html', context)
